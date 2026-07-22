from collections import defaultdict

from sqlalchemy.orm import Session

from immich_dog_tagger.models import CropClassification
from immich_dog_tagger.services.albums import AlbumService


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
    ) -> dict[str, int]:
        assets: dict[str, list[str]] = defaultdict(list)

        classifications = self.session.query(CropClassification).all()

        for classification in classifications:
            identity = classification.identity or "Unknown"

            asset_id = classification.crop.detection.asset.immich_asset_id

            assets[identity].append(asset_id)

        summary = {}

        for identity, asset_ids in assets.items():
            unique_ids = list(set(asset_ids))

            if not dry_run:
                self.albums.sync_identity(
                    identity,
                    unique_ids,
                )

            summary[identity] = len(unique_ids)

        return summary
