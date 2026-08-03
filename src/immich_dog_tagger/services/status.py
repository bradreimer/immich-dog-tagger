"""
Pipeline health and status reporting.
"""

from collections import Counter
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from immich_dog_tagger.enums import (
    AssetStatus,
    EmbeddingSources,
    ReviewActions,
)
from immich_dog_tagger.models import (
    Asset,
    Crop,
    CropClassification,
    Detection,
    EmbeddingExample,
    Identity,
    ReviewAction,
)


@dataclass(frozen=True)
class StatusSummary:
    assets: int
    statuses: dict[str, int]

    identities: int
    examples: int

    examples_by_source: dict[str, int]
    review_actions_by_type: dict[str, int]

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


@dataclass(frozen=True)
class PipelinePlan:
    pending_download: int
    pending_detection: int
    pending_classification: int


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
            examples_by_source=self._count_examples_by_source(),
            review_actions_by_type=self._count_review_actions_by_type(),
            pending_download=self._count_pending_download(),
            downloaded=self._count_downloaded(),
            download_failed=self._count_download_failed(),
            detections=self._count(Detection),
            pending_detection=self._count_pending_detection(),
            detection_failed=self._count_detection_failed(),
            crops=self._count(Crop),
            classifications=self._count(CropClassification),
            pending_classification=self._count_pending_classification(),
            classification_failed=self._count_classification_failed(),
            unknown=self._count_unknown(),
            low_confidence=self._count_low_confidence(
                confidence_threshold,
            ),
        )

    def pipeline_plan(self) -> PipelinePlan:
        return PipelinePlan(
            pending_download=self._count_pending_download(),
            pending_detection=self._count_pending_detection(),
            pending_classification=self._count_pending_classification(),
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
                    Asset.status == AssetStatus.PENDING,
                )
            )
            or 0
        )

    def _count_downloaded(self) -> int:
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

    def _count_download_failed(self) -> int:
        return (
            self.session.scalar(
                select(func.count())
                .select_from(Asset)
                .where(
                    Asset.status == AssetStatus.DOWNLOAD_FAILED,
                )
            )
            or 0
        )

    def _count_detection_failed(self) -> int:
        return (
            self.session.scalar(
                select(func.count())
                .select_from(Asset)
                .where(
                    Asset.status == AssetStatus.DETECTION_FAILED,
                )
            )
            or 0
        )

    def _count_classification_failed(self) -> int:
        return (
            self.session.scalar(
                select(func.count())
                .select_from(Asset)
                .where(
                    Asset.status == AssetStatus.CLASSIFICATION_FAILED,
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

    def _count_examples_by_source(self) -> dict[str, int]:
        rows = self.session.execute(
            select(
                EmbeddingExample.source,
                func.count(),
            ).group_by(
                EmbeddingExample.source,
            )
        )

        counts = {source.value: count for source, count in rows}

        return {
            source.value: counts.get(source.value, 0) for source in EmbeddingSources
        }

    def _count_review_actions_by_type(self) -> dict[str, int]:
        rows = self.session.execute(
            select(
                ReviewAction.action,
                func.count(),
            ).group_by(
                ReviewAction.action,
            )
        )

        counts = {action.value: count for action, count in rows}

        return {action.value: counts.get(action.value, 0) for action in ReviewActions}
