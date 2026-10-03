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

A photo Immich no longer has (issue #370) can't be repaired, only retired:
Repair marks it AssetStatus.REMOVED -- the same terminal state a full scan
reconciles deleted photos to (issue #194) -- so it leaves Review instead of
staying there broken until the next scan.
"""

import logging
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from immich_dog_tagger.downloader import Downloader
from immich_dog_tagger.enums import AssetStatus, ClassificationMode
from immich_dog_tagger.immich import ImmichAssetNotFoundError, ImmichGetAssetError
from immich_dog_tagger.models import Asset
from immich_dog_tagger.scanner import apply_immich_metadata, mark_asset_removed
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
    # False when the repair stopped at a handled failure (issue #386), so a
    # batch caller can tell it from a real repair without parsing `message`.
    # True for a removed photo: retiring it is the intended outcome.
    succeeded: bool = True
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
        account_id: int | None = None,
        action: str = "Repair",
    ):
        self.session = session
        # Names the action in failure messages: "Repair", or "Look harder"
        # when this runs with the open-vocabulary detector (issue #390).
        self.action = action
        # Issue #346/#370: which configured account downloader.client's API
        # key belongs to. Immich answers "not found" for another account's
        # asset too, so only an asset from this account (or one with no
        # account recorded) is ever marked removed on that answer.
        self.account_id = account_id
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
        except ImmichAssetNotFoundError as e:
            if not self._client_owns(asset):
                return self._result(
                    asset,
                    succeeded=False,
                    message=(
                        f"{self.action} failed: this photo belongs to another "
                        f"Immich account, which {self.action} can't reach: {e}"
                    ),
                )

            mark_asset_removed(self.session, asset, self.downloader.cache_dir)
            self.session.commit()

            logger.info(
                "Repair marked asset id=%d immich_asset_id=%s removed: "
                "no longer in Immich",
                asset_id,
                immich_asset_id,
            )

            return self._result(
                asset,
                message="Removed: this photo no longer exists in Immich.",
            )
        except ImmichGetAssetError as e:
            return self._result(
                asset,
                succeeded=False,
                message=(
                    f"{self.action} failed: could not refresh photo metadata "
                    f"from Immich: {e}"
                ),
            )

        apply_immich_metadata(asset, immich_asset)
        asset.captured_at = immich_asset.captured_at
        self.session.commit()

        self.downloader.download_pending(force=True, asset_id=asset_id)
        self.session.refresh(asset)

        if asset.status == AssetStatus.DOWNLOAD_FAILED:
            return self._result(
                asset,
                succeeded=False,
                message=(
                    f"{self.action} failed: could not re-download the photo from Immich."
                ),
            )

        detected = self.detection_service.run(force=True, asset_id=asset_id)
        self.session.refresh(asset)

        if asset.status == AssetStatus.DETECTION_FAILED:
            return self._result(
                asset,
                succeeded=False,
                message=f"{self.action} failed: could not re-run detection on the photo.",
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

    def _client_owns(self, asset: Asset) -> bool:
        return (
            self.account_id is None
            or asset.account_id is None
            or asset.account_id == self.account_id
        )

    def _result(
        self,
        asset: Asset,
        message: str,
        succeeded: bool = True,
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
            succeeded=succeeded,
            captured_at=asset.captured_at,
            latitude=asset.latitude,
            longitude=asset.longitude,
            country=asset.country,
            state=asset.state,
            city=asset.city,
        )
