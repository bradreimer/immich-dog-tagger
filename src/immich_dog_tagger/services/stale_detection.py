"""
Detect and batch-repair photos whose stored detections predate the
EXIF-orientation decode fix (issues #137/#213/#220), per
docs/specs/stale-detection-auto-repair.md.

Only the 90/270-degree-rotation subset is detectable this way: those
orientations swap width and height on correction, so a detection box
computed before the fix extends past the corrected (upright) bounds while
still fitting the raw, pre-rotation dimensions -- an unambiguous geometric
fact, checkable from Immich's own EXIF metadata with no re-download or
re-detection. A 180-degree or mirrored orientation leaves width/height
unchanged, so a stale box from one of those stays in-bounds and is not
flagged (see the spec's Non-goals).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from immich_dog_tagger.enums import AssetStatus
from immich_dog_tagger.models import (
    Asset,
    Crop,
    CropClassification,
    Detection,
    ReviewAction,
)
from immich_dog_tagger.services.asset_repair import AssetRepairService

logger = logging.getLogger(__name__)

# EXIF orientation values that swap width/height on correction.
ROTATED_ORIENTATIONS = frozenset({5, 6, 7, 8})


@dataclass
class StaleDetectionReport:
    flagged_immich_asset_ids: list[str] = field(default_factory=list)
    reviewed_immich_asset_ids: list[str] = field(default_factory=list)

    @property
    def healthy(self) -> bool:
        return not self.flagged_immich_asset_ids

    @property
    def flagged(self) -> int:
        return len(self.flagged_immich_asset_ids)

    @property
    def reviewed_at_risk(self) -> int:
        return len(self.reviewed_immich_asset_ids)

    def as_dict(self) -> dict:
        return {
            "healthy": self.healthy,
            "flagged": self.flagged,
            "reviewed_at_risk": self.reviewed_at_risk,
        }


@dataclass
class StaleDetectionRepairSummary:
    repaired: int = 0
    skipped_reviewed: int = 0
    failed: int = 0

    @property
    def total(self) -> int:
        return self.repaired + self.skipped_reviewed + self.failed


class StaleDetectionService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def check(self) -> StaleDetectionReport:
        report = StaleDetectionReport()

        candidates = self.session.scalars(
            select(Asset)
            .where(
                Asset.status != AssetStatus.REMOVED,
                Asset.exif_orientation.in_(ROTATED_ORIENTATIONS),
                Asset.exif_width.is_not(None),
                Asset.exif_height.is_not(None),
                exists().where(Detection.asset_id == Asset.id),
            )
            .distinct()
        ).all()

        for asset in candidates:
            if self._has_stale_detection(asset):
                report.flagged_immich_asset_ids.append(asset.immich_asset_id)

                if self._has_review_history(asset.id):
                    report.reviewed_immich_asset_ids.append(asset.immich_asset_id)

        return report

    def _has_stale_detection(self, asset: Asset) -> bool:
        # exif_width/exif_height are the raw (pre-rotation) dimensions; a
        # 90/270-degree orientation's upright bounds are those swapped.
        upright_width = asset.exif_height
        upright_height = asset.exif_width

        detections = self.session.scalars(
            select(Detection).where(Detection.asset_id == asset.id)
        ).all()

        for detection in detections:
            out_of_upright_bounds = (
                detection.x2 > upright_width or detection.y2 > upright_height
            )
            fits_raw_bounds = (
                detection.x2 <= asset.exif_width and detection.y2 <= asset.exif_height
            )

            if out_of_upright_bounds and fits_raw_bounds:
                return True

        return False

    def _has_review_history(self, asset_id: int) -> bool:
        return self.session.scalar(
            select(
                exists(
                    select(ReviewAction.id)
                    .join(
                        CropClassification,
                        ReviewAction.classification_id == CropClassification.id,
                    )
                    .join(Crop, CropClassification.crop_id == Crop.id)
                    .join(Detection, Crop.detection_id == Detection.id)
                    .where(Detection.asset_id == asset_id)
                )
            )
        )

    def repair(
        self,
        asset_repair_service: AssetRepairService,
        include_reviewed: bool = False,
    ) -> StaleDetectionRepairSummary:
        """
        Batch-runs the existing per-photo AssetRepairService.repair() over
        every currently-flagged asset. Reviewed assets are skipped unless
        `include_reviewed` is explicitly set -- repairing one discards its
        review history (see AssetRepairService's docstring), so that has to
        be an informed, opt-in choice, never the default.
        """
        report = self.check()
        summary = StaleDetectionRepairSummary()
        reviewed = set(report.reviewed_immich_asset_ids)

        for immich_asset_id in report.flagged_immich_asset_ids:
            if immich_asset_id in reviewed and not include_reviewed:
                summary.skipped_reviewed += 1
                continue

            try:
                asset_repair_service.repair(immich_asset_id)
                summary.repaired += 1
            except Exception:
                # Isolated per-asset, mirroring DetectionService's own
                # per-asset error handling -- one bad photo shouldn't abort
                # the rest of the batch. Rolled back so a failure partway
                # through one asset's repair doesn't leave a dangling
                # transaction the next asset's repair would inherit.
                self.session.rollback()
                logger.exception(
                    "Stale-detection repair failed for asset %s", immich_asset_id
                )
                summary.failed += 1

        return summary
