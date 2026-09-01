import logging
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from .enums import AssetStatus
from .immich import ImmichAsset, ImmichClient
from .models import Asset, EmbeddingExample

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
        cache_dir: Path | None = None,
    ):
        self.client = client
        self.session = session
        self.cache_dir = cache_dir

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
        is_full_scan = limit is None

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

        # Only a full (unlimited) scan sees every asset Immich currently
        # has -- a --limit run's result set is a truncated sample, not "all
        # of Immich", so diffing it against state.db would wrongly mark
        # everything past the limit as deleted (issue #194).
        if is_full_scan:
            self._reconcile_removed(
                {immich_asset.id for immich_asset in immich_assets},
                should_cancel,
            )

        return new_count

    def _reconcile_removed(
        self,
        current_ids: set[str],
        should_cancel: Callable[[], bool] | None,
    ) -> int:
        """
        Assets state.db still considers active that this scan's full result
        set no longer contains -- i.e. deleted in Immich since the last
        scan. Moved to the terminal AssetStatus.REMOVED (FR-2) rather than
        hard-deleted, so review history/provenance referencing the row stay
        queryable; only the cached original and any crop files not backing
        an active-learning reference example (FR-5) are cleaned up from
        disk.
        """
        candidates = self.session.scalars(
            select(Asset).where(Asset.status != AssetStatus.REMOVED)
        ).all()

        removed_count = 0
        since_commit = 0

        for asset in candidates:
            if asset.immich_asset_id in current_ids:
                continue

            if should_cancel and should_cancel():
                self.session.rollback()
                return removed_count

            self._mark_removed(asset)
            removed_count += 1
            since_commit += 1

            if since_commit >= BATCH_SIZE:
                self.session.commit()
                since_commit = 0

        if since_commit:
            self.session.commit()

        if removed_count:
            logger.info(
                "Scan reconciled %d asset(s) deleted from Immich",
                removed_count,
            )

        return removed_count

    def _mark_removed(self, asset: Asset) -> None:
        asset.status = AssetStatus.REMOVED

        if self.cache_dir is not None:
            asset.cache_path(self.cache_dir).unlink(missing_ok=True)

        for detection in asset.detections:
            if detection.crop is not None:
                self._maybe_delete_crop_file(detection.crop.path)

    def _maybe_delete_crop_file(self, crop_path: str) -> None:
        in_use = self.session.scalar(
            select(EmbeddingExample.id).where(
                EmbeddingExample.crop_path == crop_path,
            )
        )

        if in_use is not None:
            # Retained: still backing an active-learning reference example
            # (FR-5) -- deleting it here would silently degrade future
            # classification quality for other photos, not just destroy
            # this asset's own review history.
            return

        Path(crop_path).unlink(missing_ok=True)

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

            if existing.status == AssetStatus.REMOVED:
                # Reappeared after being reconciled out (e.g. restored in
                # Immich). Its cache/crop files were already cleaned up, so
                # route it back through the pipeline from scratch rather
                # than leaving it stranded in a terminal state everything
                # else treats as gone for good.
                existing.checksum = immich_asset.checksum
                existing.extension = immich_asset.extension
                existing.status = AssetStatus.PENDING

                changed = 1
            elif force and existing.checksum != immich_asset.checksum:
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
