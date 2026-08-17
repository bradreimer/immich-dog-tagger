import logging
from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from .enums import AssetStatus
from .immich import ImmichAsset, ImmichClient
from .models import Asset

logger = logging.getLogger(__name__)

# Commit every this-many assets so a failure partway through a run (Immich
# hiccup, DB error, process kill) leaves fewer than this many already-
# processed assets to redo -- the next scan retries only the uncommitted
# remainder (issue #99).
BATCH_SIZE = 1000


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
        should_cancel: Callable[[], bool] | None = None,
    ) -> int:
        """
        Discover new Immich assets.

        Returns number of new assets.
        """

        immich_assets = self.client.list_assets()

        if limit is not None:
            immich_assets = immich_assets[:limit]

        new_count = 0
        committed_new_count = 0
        since_commit = 0

        for immich_asset in immich_assets:
            if should_cancel and should_cancel():
                # Discard whatever's accumulated since the last commit --
                # only fully-committed batches are kept (issue #111).
                self.session.rollback()
                return committed_new_count

            try:
                new_count += self._process_asset(immich_asset, force)
                since_commit += 1

                if since_commit >= BATCH_SIZE:
                    self.session.commit()
                    committed_new_count = new_count
                    since_commit = 0
            except Exception as exc:
                self.session.rollback()
                logger.exception(
                    "Scan failed processing Immich asset %s after %d new/"
                    "updated asset(s) already committed this run",
                    immich_asset.id,
                    committed_new_count,
                )
                raise RuntimeError(
                    f"Scan failed processing Immich asset {immich_asset.id} "
                    f"after {committed_new_count} new/updated asset(s) "
                    f"committed this run: {exc}"
                ) from exc

        self.session.commit()

        return new_count

    def _process_asset(
        self,
        immich_asset: ImmichAsset,
        force: bool,
    ) -> int:
        existing = self.session.scalar(
            select(Asset).where(Asset.immich_asset_id == immich_asset.id)
        )

        if existing:
            changed = 0

            if force and existing.checksum != immich_asset.checksum:
                existing.checksum = immich_asset.checksum
                existing.extension = immich_asset.extension
                existing.status = AssetStatus.PENDING

                changed = 1

            # Location/people/favorite are refreshed every scan
            # regardless of checksum -- they can change in Immich (a
            # newly recognized person, a toggled favorite) without the
            # photo file itself changing, and this is already the same
            # response the scan just fetched (issue #94), not an extra
            # request.
            _apply_immich_metadata(existing, immich_asset)

            return changed

        asset = Asset(
            immich_asset_id=immich_asset.id,
            checksum=immich_asset.checksum,
            extension=immich_asset.extension,
            captured_at=immich_asset.captured_at,
        )
        _apply_immich_metadata(asset, immich_asset)

        self.session.add(asset)

        return 1


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
