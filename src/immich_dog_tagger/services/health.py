"""
Pipeline health and status reporting.
"""

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from immich_dog_tagger.models import (
    Asset,
    Crop,
    CropClassification,
    Detection,
)
from immich_dog_tagger.status import AssetStatus


@dataclass(frozen=True)
class HealthSummary:
    assets: int
    downloaded: int
    detected: int
    detections: int
    crops: int
    classifications: int
    unknown: int
    low_confidence: int


class HealthService:
    def __init__(
        self,
        session: Session,
    ):
        self.session = session

    def summary(
        self,
        *,
        confidence_threshold: float = 0.80,
    ) -> HealthSummary:
        return HealthSummary(
            assets=self._count(Asset),
            downloaded=self._count_assets(AssetStatus.DOWNLOADED),
            detected=self._count_assets(AssetStatus.DETECTED),
            detections=self._count(Detection),
            crops=self._count(Crop),
            classifications=self._count(CropClassification),
            unknown=self._count_unknown(),
            low_confidence=self._count_low_confidence(
                confidence_threshold,
            ),
        )

    def _count(
        self,
        model,
    ) -> int:
        return self.session.scalar(select(func.count()).select_from(model)) or 0

    def _count_assets(
        self,
        status: AssetStatus,
    ) -> int:
        return (
            self.session.scalar(
                select(func.count()).select_from(Asset).where(Asset.status == status)
            )
            or 0
        )

    def _count_unknown(self) -> int:
        return (
            self.session.scalar(
                select(func.count())
                .select_from(CropClassification)
                .where(CropClassification.identity.is_(None))
            )
            or 0
        )

    def _count_low_confidence(
        self,
        threshold: float,
    ) -> int:
        return (
            self.session.scalar(
                select(func.count())
                .select_from(CropClassification)
                .where(
                    CropClassification.confidence < threshold,
                )
            )
            or 0
        )
