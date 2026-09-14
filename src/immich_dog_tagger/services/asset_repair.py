"""
Reprocess a single asset's detect/crop/embed/classify pipeline, and refresh
its Immich-cached metadata, (issues #226, #326).

For a photo whose stored Detection coordinates predate an EXIF-orientation
fix (issues #137/#213/#220), the stored data itself is stale -- no amount of
re-viewing fixes it. This forces one asset back through download -> detect ->
classify against its current cached original, replacing whatever Detection/
Crop/CropClassification rows exist for it. It also refreshes this asset's
captured_at/location/favorite/people/exif fields from Immich's current
values (issue #326) -- a full library scan() already does this for every
asset but Repair never did for just the one being looked at, and captured_at
specifically is never refreshed by scan() either, even for an existing row.

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
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from immich_dog_tagger.downloader import Downloader
from immich_dog_tagger.enums import AssetStatus, ClassificationMode
from immich_dog_tagger.immich import ImmichGetAssetError
from immich_dog_tagger.models import Asset
from immich_dog_tagger.scanner import apply_immich_metadata
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
    captured_at: datetime | None = None
    latitude: float | None = None
    longitude: float | None = None
    country: str | None = None
    state: str | None = None
    city: str | None = None


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

        # Refreshed and committed before the destructive download/detect/
        # classify steps below: this is comparatively cheap and non-
        # destructive (issue #326), so a later pipeline failure shouldn't
        # also discard it, and a metadata-fetch failure itself is enough
        # reason to stop before attempting the rest of the pipeline.
        try:
            immich_asset = self.downloader.client.get_asset(immich_asset_id)
        except ImmichGetAssetError as e:
            return self._result(
                asset,
                message=f"Repair failed: could not refresh photo metadata from Immich: {e}",
            )

        apply_immich_metadata(asset, immich_asset)
        asset.captured_at = immich_asset.captured_at
        self.session.commit()

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
                f"{classified.classified} classified. Metadata refreshed from Immich."
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
            captured_at=asset.captured_at,
            latitude=asset.latitude,
            longitude=asset.longitude,
            country=asset.country,
            state=asset.state,
            city=asset.city,
        )
