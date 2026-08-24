"""
Reverse of the "View in Immich" link (issue #128): given an Immich asset id
pasted by the owner, find what this instance already knows about that photo
-- see docs/specs/photo-lookup.md (issue #179). Read-only: never triggers
detection/classification, only reads what a prior pipeline run already
produced.
"""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from immich_dog_tagger.models import Asset, Crop, Detection


@dataclass(frozen=True)
class PhotoLookupDetection:
    detection_id: int
    x1: int
    y1: int
    x2: int
    y2: int
    species: str
    crop_id: int | None
    classification_id: int | None
    identity: str | None
    confidence: float | None


@dataclass(frozen=True)
class PhotoLookup:
    asset_id: int
    immich_asset_id: str
    extension: str
    captured_at: datetime | None
    detections: list[PhotoLookupDetection]


class PhotoLookupService:
    def __init__(self, session: Session):
        self.session = session

    def get(self, immich_asset_id: str) -> PhotoLookup | None:
        asset = self.session.scalars(
            select(Asset)
            .options(
                selectinload(Asset.detections)
                .selectinload(Detection.crop)
                .selectinload(Crop.classification)
            )
            .where(Asset.immich_asset_id == immich_asset_id)
        ).first()

        if asset is None:
            return None

        detections = [self._to_detection(detection) for detection in asset.detections]

        return PhotoLookup(
            asset_id=asset.id,
            immich_asset_id=asset.immich_asset_id,
            extension=asset.extension,
            captured_at=asset.captured_at,
            detections=detections,
        )

    def _to_detection(self, detection: Detection) -> PhotoLookupDetection:
        crop = detection.crop
        classification = crop.classification if crop is not None else None

        return PhotoLookupDetection(
            detection_id=detection.id,
            x1=detection.x1,
            y1=detection.y1,
            x2=detection.x2,
            y2=detection.y2,
            species=crop.species.value if crop is not None else detection.label,
            crop_id=crop.id if crop is not None else None,
            classification_id=classification.id if classification is not None else None,
            identity=classification.identity if classification is not None else None,
            confidence=(
                classification.confidence if classification is not None else None
            ),
        )
