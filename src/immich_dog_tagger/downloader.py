import logging
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from .enums import AssetStatus
from .immich import ImmichClient, ImmichDownloadError
from .media import is_supported_extension
from .models import Asset

logger = logging.getLogger(__name__)

# See scanner.BATCH_SIZE -- same rationale, so scan and download share the
# same bounded-reprocessing property (issue #99).
BATCH_SIZE = 1000


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
        since_commit = 0

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
            elif self._download_one(asset, path):
                count += 1

            since_commit += 1

            if since_commit >= BATCH_SIZE:
                self._commit(since_commit)
                since_commit = 0

        self._commit(since_commit)

        return count

    def _download_one(
        self,
        asset: Asset,
        path: Path,
    ) -> bool:
        try:
            data = self.client.download_asset(asset.immich_asset_id)
            path.write_bytes(data)
        except ImmichDownloadError as exc:
            asset.status = AssetStatus.DOWNLOAD_FAILED
            logger.warning(
                "Download failed for asset id=%s immich_asset_id=%s: %s",
                asset.id,
                asset.immich_asset_id,
                exc,
            )
            return False
        except Exception:
            # Anything unexpected -- a disk write failure, a connection
            # reset that isn't wrapped as ImmichDownloadError -- shouldn't
            # take the rest of the batch down with it (issue #99): record
            # it on this asset the same way and move on.
            asset.status = AssetStatus.DOWNLOAD_FAILED
            logger.exception(
                "Unexpected error downloading asset id=%s immich_asset_id=%s",
                asset.id,
                asset.immich_asset_id,
            )
            return False

        asset.status = AssetStatus.DOWNLOADED
        return True

    def _commit(
        self,
        batch_size: int,
    ) -> None:
        if batch_size == 0:
            return

        try:
            self.session.commit()
        except Exception as exc:
            self.session.rollback()
            logger.exception(
                "Failed to commit a batch of %d downloaded asset(s)",
                batch_size,
            )
            raise RuntimeError(
                f"Failed to commit a batch of {batch_size} downloaded asset(s): {exc}"
            ) from exc
