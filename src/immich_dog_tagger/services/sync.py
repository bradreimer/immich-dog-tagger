from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from immich_dog_tagger.models import CropClassification
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

        return SyncSummary(
            identities=summary,
        )
