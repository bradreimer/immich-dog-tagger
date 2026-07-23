"""
Pipeline health and status reporting.
"""

from dataclasses import dataclass
from collections import Counter

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from immich_dog_tagger.models import (
    Asset,
    Crop,
    CropClassification,
    Detection,
    EmbeddingExample,
    Identity,
)
from immich_dog_tagger.enums import AssetStatus


@dataclass(frozen=True)
class StatusSummary:
    assets: int
    statuses: dict[str, int]

    identities: int
    examples: int

    pending_download: int
    downloaded: int
    download_failed: int

    detections: int
    pending_detection: int
    detection_failed: int

    crops: int

    classifications: int
    pending_classification: int
    classification_failed: int

    unknown: int
    low_confidence: int


class StatusService:
    def __init__(
        self,
        session: Session,
    ):
        self.session = session

    def summary(
        self,
        *,
        confidence_threshold: float = 0.80,
    ) -> StatusSummary:
        return StatusSummary(
            assets=self._count(Asset),
            statuses=self._asset_status_counts(),
            identities=self._count(Identity),
            examples=self._count(EmbeddingExample),
            pending_download=self._count_assets(
                AssetStatus.PENDING,
            ),
            downloaded=self._count_assets(
                AssetStatus.DOWNLOADED,
            ),
            download_failed=self._count_assets(
                AssetStatus.DOWNLOAD_FAILED,
            ),
            detections=self._count(Detection),
            pending_detection=self._count_assets(
                AssetStatus.DOWNLOADED,
            ),
            detection_failed=self._count_assets(
                AssetStatus.DETECTION_FAILED,
            ),
            crops=self._count(Crop),
            classifications=self._count(CropClassification),
            pending_classification=self._count_pending_classification(),
            classification_failed=self._count_assets(
                AssetStatus.CLASSIFICATION_FAILED,
            ),
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

    def _asset_status_counts(self) -> dict[str, int]:
        assets = self.session.scalars(select(Asset)).all()

        counts = Counter()

        for asset in assets:
            counts[asset.status.value] += 1

        return dict(counts)

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

    def _count_pending_download(self) -> int:
        return (
            self.session.scalar(
                select(func.count())
                .select_from(Asset)
                .where(
                    Asset.status == AssetStatus.NEW,
                )
            )
            or 0
        )

    def _count_pending_detection(self) -> int:
        return (
            self.session.scalar(
                select(func.count())
                .select_from(Asset)
                .where(
                    Asset.status == AssetStatus.DOWNLOADED,
                )
            )
            or 0
        )

    def _count_pending_classification(self) -> int:
        return (
            self.session.scalar(
                select(func.count())
                .select_from(Crop)
                .where(
                    ~Crop.classification.has(),
                )
            )
            or 0
        )
