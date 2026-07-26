from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from immich_dog_tagger.models import CropClassification
from immich_dog_tagger.services.albums import AlbumService


@dataclass(frozen=True)
class SyncIdentitySummary:
    identity: str
    assets: int


@dataclass(frozen=True)
class SyncSummary:
    identities: list[SyncIdentitySummary]


class SyncService:
    def __init__(
        self,
        session: Session,
        albums: AlbumService,
    ):
        self.session = session
        self.albums = albums

    def sync(
        self,
        *,
        dry_run: bool = False,
    ) -> SyncSummary:
        assets: dict[str, set[str]] = defaultdict(set)

        classifications = self.session.scalars(select(CropClassification)).all()

        for classification in classifications:
            identity = classification.identity or "Unknown"

            asset_id = classification.crop.detection.asset.immich_asset_id

            assets[identity].add(asset_id)

        summary: list[SyncIdentitySummary] = []

        for identity, asset_ids in assets.items():
            if not dry_run:
                self.albums.sync_identity(
                    identity,
                    sorted(asset_ids),
                )

            summary.append(
                SyncIdentitySummary(
                    identity=identity,
                    assets=len(asset_ids),
                )
            )

        return SyncSummary(
            identities=summary,
        )
