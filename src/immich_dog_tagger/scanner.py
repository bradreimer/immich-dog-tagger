from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from .enums import AssetStatus
from .immich import ImmichAsset, ImmichClient
from .models import Asset


class Scanner:
    def __init__(
        self,
        client: ImmichClient,
        session: Session,
    ):
        self.client = client
        self.session = session

    def scan(
        self,
        limit: int | None = None,
        force: bool = False,
    ) -> int:
        """
        Discover new Immich assets.

        Returns number of new assets.
        """

        immich_assets = self.client.list_assets()

        if limit is not None:
            immich_assets = immich_assets[:limit]

        new_count = 0

        for immich_asset in immich_assets:
            existing = self.session.scalar(
                select(Asset).where(Asset.immich_asset_id == immich_asset.id)
            )

            if existing:
                if force and existing.checksum != immich_asset.checksum:
                    existing.checksum = immich_asset.checksum
                    existing.extension = immich_asset.extension
                    existing.status = AssetStatus.PENDING

                    new_count += 1

                # Location/people/favorite are refreshed every scan
                # regardless of checksum -- they can change in Immich (a
                # newly recognized person, a toggled favorite) without the
                # photo file itself changing, and this is already the same
                # response the scan just fetched (issue #94), not an extra
                # request.
                _apply_immich_metadata(existing, immich_asset)

                continue

            asset = Asset(
                immich_asset_id=immich_asset.id,
                checksum=immich_asset.checksum,
                extension=immich_asset.extension,
                captured_at=immich_asset.captured_at,
            )
            _apply_immich_metadata(asset, immich_asset)

            self.session.add(asset)

            new_count += 1

        self.session.commit()

        return new_count


def _apply_immich_metadata(asset: Asset, immich_asset: ImmichAsset) -> None:
    asset.latitude = immich_asset.latitude
    asset.longitude = immich_asset.longitude
    asset.country = immich_asset.country
    asset.state = immich_asset.state
    asset.city = immich_asset.city
    asset.is_favorite = immich_asset.is_favorite
    asset.people = [
        {"id": person.id, "name": person.name} for person in immich_asset.people
    ]
    asset.metadata_synced_at = datetime.now(UTC).replace(tzinfo=None)
