import logging
from collections import defaultdict
from dataclasses import dataclass, field

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
from immich_dog_tagger.services.tags import TagService

logger = logging.getLogger(__name__)

# Referenced from a failed sync's user-facing message (issue #259) so a permission-denied
# failure -- Immich rejecting a bulk album/tag write with `no_permission` -- points straight at
# the exact Immich API key permissions Sync needs, instead of leaving the operator to guess.
IMMICH_PERMISSIONS_DOC_URL = "https://github.com/bradreimer/immich-dog-tagger/blob/main/docs/immich-api-key-permissions.md"


@dataclass(frozen=True)
class SyncIdentitySummary:
    identity: str
    species: str
    assets: int
    # True when this identity's failure was Immich rejecting the write with `no_permission`
    # (issue #259) -- e.g. a missing `tag.asset` grant on the API key -- rather than some other
    # failure (timeout, transient error). Always False for a non-failed identity.
    permission_error: bool = False


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
    # Identities whose album/tag membership write raised this run (e.g. an Immich timeout on a
    # large batch, issue #243) rather than one bad identity aborting the whole job silently.
    # Their previous SyncedAsset tracking is left untouched so the next sync retries them.
    failed_identities: list[SyncIdentitySummary] = field(default_factory=list)


class SyncService:
    def __init__(
        self,
        session: Session,
        albums: AlbumService,
        policy: SyncPolicy | None = None,
        tags: TagService | None = None,
    ):
        self.session = session
        self.albums = albums
        self.policy = policy or SyncPolicy()
        self.tags = tags

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

        previous: dict[tuple[str, str], set[str]] = {}
        # Maps a failed (species, identity) key to whether the failure was Immich rejecting the
        # write with `no_permission` (issue #259) -- surfaced per-identity so the final summary
        # can tell a permission problem apart from a transient one (e.g. a timeout, #243).
        failed: dict[tuple[str, str], bool] = {}

        if not dry_run:
            previous = self._previously_synced_state()
            failed |= self._remove_stale_memberships(assets, previous)

        summary: list[SyncIdentitySummary] = []
        failed_summary: list[SyncIdentitySummary] = []

        for (species, identity), asset_ids in assets.items():
            if not dry_run:
                try:
                    self.albums.sync_identity(
                        identity,
                        sorted(asset_ids),
                        species=species,
                    )

                    if self.tags is not None:
                        self.tags.sync_identity(
                            identity,
                            sorted(asset_ids),
                            species=species,
                        )
                except Exception as exc:
                    # One identity's bulk membership write failing (e.g. an Immich timeout
                    # on a very large batch, issue #243) must not abort every other
                    # identity's sync in this job -- log it, mark it failed, and move on.
                    logger.exception(
                        "Sync failed for %s identity %r (%d asset(s)); its Immich "
                        "membership is unchanged and will be retried on the next sync",
                        species,
                        identity,
                        len(asset_ids),
                    )
                    failed[(species, identity)] = getattr(
                        exc, "permission_denied", False
                    )

            item = SyncIdentitySummary(
                identity=identity,
                species=species,
                assets=len(asset_ids),
                permission_error=failed.get((species, identity), False),
            )

            if (species, identity) in failed:
                failed_summary.append(item)
            else:
                summary.append(item)

        # A stale-removal failure for an identity with no current assets left at all never
        # reaches the loop above, but it still needs reporting -- otherwise it silently
        # falls out of both `identities` and `failed_identities`.
        for species, identity in set(failed) - set(assets):
            failed_summary.append(
                SyncIdentitySummary(
                    identity=identity,
                    species=species,
                    assets=len(previous.get((species, identity), set())),
                    permission_error=failed[(species, identity)],
                )
            )

        if not dry_run:
            self._save_synced_state(assets, previous, set(failed))

        return SyncSummary(
            identities=summary,
            manual_tags=manual_tag_count,
            skipped_low_confidence=skipped_low_confidence,
            skipped_unknown=skipped_unknown,
            skipped_missing_asset=skipped_missing_asset,
            failed_identities=failed_summary,
        )

    def _previously_synced_state(self) -> dict[tuple[str, str], set[str]]:
        state: dict[tuple[str, str], set[str]] = defaultdict(set)

        for row in self.session.scalars(select(SyncedAsset)).all():
            state[(row.species, row.identity)].add(row.immich_asset_id)

        return state

    def _remove_stale_memberships(
        self,
        current: dict[tuple[str, str], set[str]],
        previous: dict[tuple[str, str], set[str]],
    ) -> dict[tuple[str, str], bool]:
        """
        Diff the current (species, identity) -> asset_ids mapping against
        what was last synced (DT-1113). An asset present in a previous
        membership but absent from that same membership now -- because it
        was corrected to a different identity, or to Unknown -- needs
        removing from its old album (and, when tag sync is enabled, its old
        tag, issue #230); otherwise it silently stays attached to both the
        old and new identity forever.

        Returns the (species, identity) keys whose removal raised (issue #243), mapped to
        whether that failure was Immich rejecting it with `no_permission` (issue #259), so the
        caller can leave their previous tracked state alone rather than recording a removal that
        didn't actually happen.
        """
        failed: dict[tuple[str, str], bool] = {}

        for key, previous_ids in previous.items():
            species, identity = key
            stale = previous_ids - current.get(key, set())

            if not stale:
                continue

            try:
                self.albums.remove_from_identity(
                    identity,
                    sorted(stale),
                    species=species,
                )

                if self.tags is not None:
                    self.tags.remove_from_identity(
                        identity,
                        sorted(stale),
                        species=species,
                    )
            except Exception as exc:
                logger.exception(
                    "Failed to remove %d stale asset(s) from %s identity %r; its previous "
                    "Immich membership is left as-is and will be retried on the next sync",
                    len(stale),
                    species,
                    identity,
                )
                failed[key] = getattr(exc, "permission_denied", False)

        return failed

    def _save_synced_state(
        self,
        current: dict[tuple[str, str], set[str]],
        previous: dict[tuple[str, str], set[str]],
        failed: set[tuple[str, str]],
    ) -> None:
        self.session.execute(delete(SyncedAsset))

        for species, identity in set(current) | set(previous):
            key = (species, identity)
            # A key whose add or stale-removal raised this run (issue #243) keeps its
            # previous tracked state untouched -- its Immich membership was never
            # confirmed to match `current`, so recording `current` here would make the
            # next sync think it's already in sync and stop retrying it.
            asset_ids = (
                previous.get(key, set()) if key in failed else current.get(key, set())
            )

            for asset_id in asset_ids:
                self.session.add(
                    SyncedAsset(
                        species=species,
                        identity=identity,
                        immich_asset_id=asset_id,
                    )
                )

        self.session.commit()
