from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from immich_dog_tagger.enums import AssetStatus
from immich_dog_tagger.models import (
    CropClassification,
    ManualAssetTag,
    SyncedAsset,
)
from immich_dog_tagger.services.albums import AlbumService
from immich_dog_tagger.services.sync_policy import SyncPolicy


@dataclass(frozen=True)
class SyncIdentitySummary:
    identity: str
    species: str
    assets: int


@dataclass(frozen=True)
class SyncSummary:
    identities: list[SyncIdentitySummary]
    # Photos the detector missed that the owner tagged by hand (issue
    # #147). Counted separately so a sync that moved more assets than the
    # classifications explain is self-explanatory rather than mysterious.
    manual_tags: int = 0
    # Classifications that did not end up in any album this run, and why --
    # without these, a lower-than-expected album count is silent and
    # unexplained (github.com/bradreimer/immich-dog-tagger/issues/11).
    skipped_low_confidence: int = 0
    skipped_unknown: int = 0
    skipped_missing_asset: int = 0


class SyncService:
    def __init__(
        self,
        session: Session,
        albums: AlbumService,
        policy: SyncPolicy | None = None,
    ):
        self.session = session
        self.albums = albums
        self.policy = policy or SyncPolicy()

    def sync(
        self,
        *,
        dry_run: bool = False,
    ) -> SyncSummary:
        # Keyed by (species, identity), not identity alone (DT-1110) -- a
        # dog "Max" and a cat "Max" must sync to two separate albums, not
        # get merged into one because they share a name.
        assets: dict[tuple[str, str], set[str]] = defaultdict(set)

        skipped_low_confidence = 0
        skipped_unknown = 0
        skipped_missing_asset = 0

        classifications = self.session.scalars(select(CropClassification)).all()

        for classification in classifications:
            if classification.confidence < self.policy.minimum_confidence:
                skipped_low_confidence += 1
                continue

            if classification.identity is None:
                if not self.policy.include_unknown:
                    skipped_unknown += 1
                    continue

                identity = "Unknown"
            else:
                identity = classification.identity

            # A crop whose detection/asset chain is missing (e.g. an
            # orphaned row) previously raised here, aborting the entire
            # sync before a single album was touched -- one bad row meant
            # zero albums updated, not "every other row still synced".
            # Skip and count it instead so the rest of the batch still
            # goes through.
            detection = classification.crop.detection

            # A removed asset (issue #194/FR-6) no longer exists in Immich
            # at all -- there's no album membership left to add/maintain
            # for it, same as a genuinely missing asset row.
            if (
                detection is None
                or detection.asset is None
                or detection.asset.status == AssetStatus.REMOVED
            ):
                skipped_missing_asset += 1
                continue

            species = classification.crop.species
            asset_id = detection.asset.immich_asset_id

            assets[(species, identity)].add(asset_id)

        # Photos detection missed, tagged by hand (issue #147). Folded into
        # the same (species, identity) -> asset-id map, so they get album
        # membership, stale-membership removal and SyncedAsset tracking
        # from the existing machinery rather than a parallel path of their
        # own. A manual tag carries no confidence, so the confidence policy
        # above does not apply to it: a human said so.
        manual_tags = self.session.scalars(
            select(ManualAssetTag).order_by(ManualAssetTag.id)
        ).all()

        manual_tag_count = 0

        for tag in manual_tags:
            if tag.asset is None or tag.asset.status == AssetStatus.REMOVED:
                skipped_missing_asset += 1
                continue

            assets[(tag.species, tag.identity)].add(tag.asset.immich_asset_id)
            manual_tag_count += 1

        if not dry_run:
            self._remove_stale_memberships(assets)

        summary: list[SyncIdentitySummary] = []

        for (species, identity), asset_ids in assets.items():
            if not dry_run:
                self.albums.sync_identity(
                    identity,
                    sorted(asset_ids),
                    species=species,
                )

            summary.append(
                SyncIdentitySummary(
                    identity=identity,
                    species=species,
                    assets=len(asset_ids),
                )
            )

        if not dry_run:
            self._save_synced_state(assets)

        return SyncSummary(
            identities=summary,
            manual_tags=manual_tag_count,
            skipped_low_confidence=skipped_low_confidence,
            skipped_unknown=skipped_unknown,
            skipped_missing_asset=skipped_missing_asset,
        )

    def _previously_synced_state(self) -> dict[tuple[str, str], set[str]]:
        state: dict[tuple[str, str], set[str]] = defaultdict(set)

        for row in self.session.scalars(select(SyncedAsset)).all():
            state[(row.species, row.identity)].add(row.immich_asset_id)

        return state

    def _remove_stale_memberships(
        self,
        current: dict[tuple[str, str], set[str]],
    ) -> None:
        """
        Diff the current (species, identity) -> asset_ids mapping against
        what was last synced (DT-1113). An asset present in a previous
        membership but absent from that same membership now -- because it
        was corrected to a different identity, or to Unknown -- needs
        removing from its old album; otherwise it silently stays in both
        the old and new identity's albums forever.
        """
        previous = self._previously_synced_state()

        for key, previous_ids in previous.items():
            species, identity = key
            stale = previous_ids - current.get(key, set())

            if stale:
                self.albums.remove_from_identity(
                    identity,
                    sorted(stale),
                    species=species,
                )

    def _save_synced_state(
        self,
        current: dict[tuple[str, str], set[str]],
    ) -> None:
        self.session.execute(delete(SyncedAsset))

        for (species, identity), asset_ids in current.items():
            for asset_id in asset_ids:
                self.session.add(
                    SyncedAsset(
                        species=species,
                        identity=identity,
                        immich_asset_id=asset_id,
                    )
                )

        self.session.commit()
