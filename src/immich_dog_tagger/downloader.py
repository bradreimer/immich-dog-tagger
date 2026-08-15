from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from .enums import AssetStatus
from .immich import ImmichClient, ImmichDownloadError
from .media import is_supported_extension
from .models import Asset


class Downloader:
    def __init__(
        self,
        client: ImmichClient,
        session: Session,
        cache_dir: Path,
    ):
        self.client = client
        self.session = session
        self.cache_dir = cache_dir

    def download_pending(
        self,
        limit: int | None = None,
        force: bool = False,
    ) -> int:
        if force:
            query = select(Asset)
        else:
            query = select(Asset).where(Asset.status == AssetStatus.PENDING)

        if limit is not None:
            query = query.limit(limit)

        assets = self.session.scalars(query).all()

        count = 0

        self.cache_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        for asset in assets:
            path = asset.cache_path(self.cache_dir)

            if not is_supported_extension(asset.extension):
                # detect can never process this file type, so downloading
                # it would just waste space -- covers both a freshly
                # scanned asset and (via force) an already-downloaded one
                # from before this check existed.
                asset.status = AssetStatus.UNSUPPORTED

                if path.exists():
                    path.unlink()

                continue

            try:
                data = self.client.download_asset(asset.immich_asset_id)
            except ImmichDownloadError:
                asset.status = AssetStatus.DOWNLOAD_FAILED
                continue

            path.write_bytes(data)

            asset.status = AssetStatus.DOWNLOADED

            count += 1

        self.session.commit()

        return count
