from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from immich_dog_tagger.models import CropClassification, SyncedAsset
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

        classifications = self.session.scalars(select(CropClassification)).all()

        for classification in classifications:
            if classification.confidence < self.policy.minimum_confidence:
                continue

            if classification.identity is None:
                if not self.policy.include_unknown:
                    continue

                identity = "Unknown"
            else:
                identity = classification.identity

            species = classification.crop.species
            asset_id = classification.crop.detection.asset.immich_asset_id

            assets[(species, identity)].add(asset_id)

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
