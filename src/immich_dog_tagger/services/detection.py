import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from immich_dog_tagger.crops import CropWriter
from immich_dog_tagger.detector import ObjectDetector
from immich_dog_tagger.enums import AssetStatus, Species
from immich_dog_tagger.media import is_supported_image
from immich_dog_tagger.models import Asset, Crop, Detection

logger = logging.getLogger(__name__)

# See scanner.BATCH_SIZE -- same rationale (issue #99), extended to `detect`
# because a single commit at the end of the whole run held state.db's write
# lock for the run's entire duration, blocking every other reader (issue
# #104; WAL mode, issue #107, has since made reader-vs-writer concurrent,
# but SQLite still allows only one writer at a time). Kept much smaller
# than scan/download's 1000: this is GPU/CPU-bound ML inference, so a batch
# can take minutes rather than seconds, and a should_cancel() cancellation
# request (issue #111) is itself a writer -- it has to wait for whichever
# batch is currently open to commit and release SQLite's write lock, which
# must stay comfortably under the 30s busy_timeout (database.py) for a
# Cancel click to feel responsive.
BATCH_SIZE = 50


@dataclass
class DetectionSummary:
    processed: int
    detections: int
    dogs: int
    cats: int
    # Assets whose detection failed and were routed to DOWNLOAD_FAILED
    # (missing cached original -- issue #194/FR-8) or DETECTION_FAILED
    # (any other error -- FR-9) instead of aborting the batch/job.
    failed: int = 0


class DetectionService:
    def __init__(
        self,
        detector: ObjectDetector,
        session: Session,
        cache_dir: Path,
        crop_writer: CropWriter | None = None,
    ):
        self.detector = detector
        self.session = session
        self.cache_dir = cache_dir
        self.crop_writer = crop_writer

    def run(
        self,
        limit: int | None = None,
        force: bool = False,
        should_cancel: Callable[[], bool] | None = None,
        asset_id: int | None = None,
    ) -> DetectionSummary:

        query = select(Asset).where(
            Asset.status == AssetStatus.DOWNLOADED,
            ~exists().where(Detection.asset_id == Asset.id),
        )

        if force:
            query = select(Asset).where(
                Asset.status.in_(
                    [
                        AssetStatus.DOWNLOADED,
                        AssetStatus.DETECTED,
                    ]
                )
            )

        # Scopes to a single asset (issue #226's per-photo Repair action),
        # overriding the status filters above the same way `force` does --
        # a repair has to work whatever state the asset is in.
        if asset_id is not None:
            query = select(Asset).where(Asset.id == asset_id)

        if limit is not None:
            query = query.limit(limit)

        assets = self.session.scalars(query).all()

        processed = 0
        detection_count = 0
        dog_count = 0
        cat_count = 0
        failed_count = 0
        committed_processed = 0
        committed_detection_count = 0
        committed_dog_count = 0
        committed_cat_count = 0
        committed_failed_count = 0
        since_commit = 0
        pending_unlinks: list[tuple[str, Path]] = []

        for asset in assets:
            if should_cancel and should_cancel():
                # Discard whatever's accumulated since the last commit, and
                # the cache-file removals queued for it -- those assets
                # revert to DOWNLOADED, so their cache file must still
                # exist for a future detect run (issue #111).
                self.session.rollback()
                pending_unlinks.clear()

                return DetectionSummary(
                    processed=committed_processed,
                    detections=committed_detection_count,
                    dogs=committed_dog_count,
                    cats=committed_cat_count,
                    failed=committed_failed_count,
                )

            image_path = asset.cache_path(self.cache_dir)

            if not is_supported_image(image_path):
                continue

            if force:
                existing = self.session.scalars(
                    select(Detection).where(
                        Detection.asset_id == asset.id,
                    )
                ).all()

                for detection in existing:
                    if detection.crop:
                        crop_path = Path(detection.crop.path)

                        if crop_path.exists():
                            crop_path.unlink()

                    self.session.delete(detection)

                self.session.flush()

            if not image_path.exists():
                # The cached original is gone -- most likely a state.db
                # restore against a since-cleaned cache directory, or the
                # cache dir cleared out of band. Route back to
                # DOWNLOAD_FAILED (issue #194/FR-8): Downloader.download_pending()
                # already includes that status in its default query, so the
                # pipeline's own next download batch re-fetches it instead
                # of this asset failing identically on every retry.
                asset.status = AssetStatus.DOWNLOAD_FAILED
                logger.warning(
                    "Missing cached original for asset %s (%s); routed back "
                    "to download_failed for re-download",
                    asset.immich_asset_id,
                    image_path,
                )
                failed_count += 1
                since_commit += 1

                if since_commit >= BATCH_SIZE:
                    self._commit(since_commit)
                    committed_processed = processed
                    committed_detection_count = detection_count
                    committed_dog_count = dog_count
                    committed_cat_count = cat_count
                    committed_failed_count = failed_count
                    since_commit = 0
                    self._unlink_all(pending_unlinks)
                    pending_unlinks.clear()

                continue

            try:
                detections = self.detector.detect(str(image_path))

                crop_map: dict[int, Path] = {}

                if self.crop_writer:
                    crop_results = self.crop_writer.write(
                        image_path,
                        asset.immich_asset_id,
                        detections,
                    )

                    crop_map = dict(crop_results)
            except Exception:
                # Isolated to this asset (issue #194/FR-7), mirroring
                # Downloader._download_one(): nothing has been added to the
                # session for this asset yet, so there is nothing to roll
                # back -- record the failure and move on to the rest of the
                # batch/job instead of aborting it.
                asset.status = AssetStatus.DETECTION_FAILED

                # A bare exception message (e.g. a Pillow decoding error)
                # gives no way to tell which asset caused it without
                # reproducing the failure -- fold that context into the log
                # (with a traceback) the same way the job's error_message
                # used to, so it's still diagnosable now that it no longer
                # aborts the job.
                logger.exception(
                    "Detection failed for asset %s (%s)",
                    asset.immich_asset_id,
                    image_path,
                )
                failed_count += 1
                since_commit += 1

                if since_commit >= BATCH_SIZE:
                    self._commit(since_commit)
                    committed_processed = processed
                    committed_detection_count = detection_count
                    committed_dog_count = dog_count
                    committed_cat_count = cat_count
                    committed_failed_count = failed_count
                    since_commit = 0
                    self._unlink_all(pending_unlinks)
                    pending_unlinks.clear()

                continue

            for index, detection in enumerate(detections):
                detection_count += 1

                if detection.label == "dog":
                    dog_count += 1
                elif detection.label == "cat":
                    cat_count += 1

                db_detection = Detection(
                    asset_id=asset.id,
                    label=detection.label,
                    confidence=detection.confidence,
                    x1=detection.x1,
                    y1=detection.y1,
                    x2=detection.x2,
                    y2=detection.y2,
                )

                self.session.add(db_detection)

                self.session.flush()

                crop_path = crop_map.get(index)

                if crop_path:
                    self.session.add(
                        Crop(
                            detection_id=db_detection.id,
                            path=str(crop_path),
                            species=Species(detection.label),
                        )
                    )

            asset.status = AssetStatus.DETECTED

            processed += 1
            since_commit += 1

            if self.crop_writer:
                # The original is only needed to run detection -- embed,
                # classify, and sync never touch it again once crops
                # exist. Removing it here is the main lever for keeping
                # cache_dir proportional to what's actually needed rather
                # than to the whole library; a future `detect --force` on
                # this asset needs `download --force` first to get it back.
                # Deferred until this asset's batch actually commits (issue
                # #111) -- unlinking immediately meant a rolled-back batch
                # (a mid-batch failure, or now a cancellation) could leave
                # an asset back at DOWNLOADED with its cache file already
                # gone, and download_pending() only re-fetches PENDING/
                # DOWNLOAD_FAILED assets, so it would get stuck.
                pending_unlinks.append((asset.immich_asset_id, image_path))

            if since_commit >= BATCH_SIZE:
                self._commit(since_commit)
                committed_processed = processed
                committed_detection_count = detection_count
                committed_dog_count = dog_count
                committed_cat_count = cat_count
                committed_failed_count = failed_count
                since_commit = 0
                self._unlink_all(pending_unlinks)
                pending_unlinks.clear()

        self._commit(since_commit)
        self._unlink_all(pending_unlinks)

        return DetectionSummary(
            processed=processed,
            detections=detection_count,
            dogs=dog_count,
            cats=cat_count,
            failed=failed_count,
        )

    def _unlink_all(
        self,
        pending_unlinks: list[tuple[str, Path]],
    ) -> None:
        for immich_asset_id, image_path in pending_unlinks:
            try:
                image_path.unlink(missing_ok=True)
            except OSError:
                logger.warning(
                    "Failed to remove cached original after detection: "
                    "asset=%s image=%s",
                    immich_asset_id,
                    image_path,
                )

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
                "Failed to commit a batch of %d detected asset(s)",
                batch_size,
            )
            raise RuntimeError(
                f"Failed to commit a batch of {batch_size} detected asset(s): {exc}"
            ) from exc
