"""
Reprocess a single asset's detect/crop/embed/classify pipeline (issue #226).

For a photo whose stored Detection coordinates predate an EXIF-orientation
fix (issues #137/#213/#220), the stored data itself is stale -- no amount of
re-viewing fixes it. This forces one asset back through download -> detect ->
classify against its current cached original, replacing whatever Detection/
Crop/CropClassification rows exist for it.

Deliberately per-asset and human-triggered (a "Repair" action on the Review
or Photo Lookup page for the one photo being looked at), never run
automatically across the library: DetectionService.run(force=True) deletes
and recreates Detection rows, which cascades (see models.py) to delete any
CropClassification and ReviewAction rows already recorded against them --
i.e. repairing a reviewed photo discards its review history. That's an
accepted, visible cost of an explicit per-photo action, not something to
silently do library-wide.
"""

import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from immich_dog_tagger.downloader import Downloader
from immich_dog_tagger.enums import AssetStatus, ClassificationMode
from immich_dog_tagger.models import Asset
from immich_dog_tagger.services.classification import ClassificationService
from immich_dog_tagger.services.detection import DetectionService

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AssetRepairResult:
    asset_id: int
    immich_asset_id: str
    status: AssetStatus
    detections: int
    dogs: int
    cats: int
    classified: int
    message: str


class AssetRepairService:
    def __init__(
        self,
        session: Session,
        downloader: Downloader,
        detection_service: DetectionService,
        classification_service: ClassificationService,
    ):
        self.session = session
        self.downloader = downloader
        self.detection_service = detection_service
        self.classification_service = classification_service

    def repair(self, immich_asset_id: str) -> AssetRepairResult:
        asset = self.session.scalar(
            select(Asset).where(Asset.immich_asset_id == immich_asset_id)
        )

        if asset is None:
            raise ValueError(f"No scanned asset for Immich asset {immich_asset_id}")

        asset_id = asset.id

        self.downloader.download_pending(force=True, asset_id=asset_id)
        self.session.refresh(asset)

        if asset.status == AssetStatus.DOWNLOAD_FAILED:
            return self._result(
                asset,
                message="Repair failed: could not re-download the photo from Immich.",
            )

        detected = self.detection_service.run(force=True, asset_id=asset_id)
        self.session.refresh(asset)

        if asset.status == AssetStatus.DETECTION_FAILED:
            return self._result(
                asset,
                message="Repair failed: could not re-run detection on the photo.",
            )

        classified = self.classification_service.classify(
            mode=ClassificationMode.PENDING,
            asset_id=asset_id,
        )

        logger.info(
            "Repaired asset id=%d immich_asset_id=%s: %d detection(s), %d classified",
            asset_id,
            immich_asset_id,
            detected.detections,
            classified.classified,
        )

        return self._result(
            asset,
            detections=detected.detections,
            dogs=detected.dogs,
            cats=detected.cats,
            classified=classified.classified,
            message=(
                f"Repaired: {detected.detections} detection(s) found, "
                f"{classified.classified} classified."
            ),
        )

    def _result(
        self,
        asset: Asset,
        message: str,
        detections: int = 0,
        dogs: int = 0,
        cats: int = 0,
        classified: int = 0,
    ) -> AssetRepairResult:
        return AssetRepairResult(
            asset_id=asset.id,
            immich_asset_id=asset.immich_asset_id,
            status=asset.status,
            detections=detections,
            dogs=dogs,
            cats=cats,
            classified=classified,
            message=message,
        )
