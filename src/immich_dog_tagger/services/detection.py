import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from immich_dog_tagger.crops import CropWriter
from immich_dog_tagger.detector import ObjectDetector
from immich_dog_tagger.enums import AssetStatus, DetectorKind, Species
from immich_dog_tagger.images import upright_size
from immich_dog_tagger.media import is_supported_image
from immich_dog_tagger.models import Asset, Crop, Detection
from immich_dog_tagger.services.crop_files import discard_crop_file

logger = logging.getLogger(__name__)

# Each asset commits on its own (issues #104, #111, #418). SQLite allows one
# writer at a time and the write lock is held from an open transaction's first
# write until its commit, so batching commits kept the lock across every
# inference in the batch -- minutes of CPU/GPU work -- and any other writer
# (a Cancel click, creating a dog, a review correction) hit the 30s
# busy_timeout and failed with "database is locked". Committing per asset
# holds the lock only for one asset's row writes. WAL mode makes the commit
# itself cheap, and a cancel now keeps every asset already detected.


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
        # Recorded on every Detection this run creates (issue #390). A
        # duck-typed detector without `kind` stands in for YOLO.
        self.detector_kind: DetectorKind = getattr(detector, "kind", DetectorKind.YOLO)
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
                ),
                # Issue #390: a photo an owner ran "Look harder" on keeps
                # those detections through a batch re-detect. Only an
                # explicit per-photo Repair/Look harder (asset_id below)
                # replaces them.
                ~exists().where(
                    Detection.asset_id == Asset.id,
                    Detection.detector != DetectorKind.YOLO.value,
                ),
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

        for asset in assets:
            if should_cancel and should_cancel():
                break

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
                        # Keeps a file a learned example still uses (issue #380).
                        discard_crop_file(self.session, detection.crop.path)

                    self.session.delete(detection)

                # Committed now, not left pending: the delete's flush would
                # otherwise hold the write lock through this asset's
                # inference (issue #418).
                self._commit(1)

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

                self._commit(1)

                continue

            try:
                # `None` when Immich's exif dimensions haven't been cached
                # for this asset (scanned before the stale-detection spec
                # added them) -- open_upright() falls back to its old,
                # always-correct-for-non-HEIC behavior in that case.
                expected_size = upright_size(
                    asset.exif_width, asset.exif_height, asset.exif_orientation
                )
                size_kwargs = (
                    {"expected_size": expected_size}
                    if expected_size is not None
                    else {}
                )

                detections = self.detector.detect(str(image_path), **size_kwargs)

                crop_map: dict[int, Path] = {}

                if self.crop_writer:
                    crop_results = self.crop_writer.write(
                        image_path,
                        asset.immich_asset_id,
                        detections,
                        **size_kwargs,
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

                self._commit(1)

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
                    detector=self.detector_kind.value,
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
            # Issue #386: these detections came from open_upright(), so the
            # stale-detection check must never flag them as pre-fix.
            asset.upright_detected_at = datetime.now(UTC).replace(tzinfo=None)

            processed += 1

            self._commit(1)

            if self.crop_writer:
                # The original is only needed to run detection -- embed,
                # classify, and sync never touch it again once crops
                # exist. Removing it here is the main lever for keeping
                # cache_dir proportional to what's actually needed rather
                # than to the whole library; a future `detect --force` on
                # this asset needs `download --force` first to get it back.
                # Only after the commit (issue #111): the asset must be
                # recorded as DETECTED before its cache file goes away, or a
                # failed commit would leave it DOWNLOADED with no original.
                self._unlink_all([(asset.immich_asset_id, image_path)])

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
