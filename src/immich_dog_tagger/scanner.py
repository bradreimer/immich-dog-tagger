from sqlalchemy import select
from sqlalchemy.orm import Session

from .immich import ImmichClient
from .models import Asset
from .status import AssetStatus


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

                continue

            self.session.add(
                Asset(
                    immich_asset_id=immich_asset.id,
                    checksum=immich_asset.checksum,
                    extension=immich_asset.extension,
                )
            )

            new_count += 1

        self.session.commit()

        return new_count
