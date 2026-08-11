"""
Learning-progress metrics.

Answers the question v1.0.0 exists to answer: is manual review becoming
less necessary? Every count states its own denominator/scope explicitly
(see LearningMetrics fields) rather than presenting a bare percentage.
Precision/accuracy are intentionally not computed here -- they would
require a held-out evaluation set distinct from the reviews used as
ground truth, which does not exist in v1.0.0.
"""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from immich_dog_tagger.models import (
    ClassificationPass,
    CropClassification,
    EmbeddingExample,
)
from immich_dog_tagger.policy import DEFAULT_POLICY, ClassifierPolicy
from immich_dog_tagger.services.review_query import ReviewQueryService


@dataclass(frozen=True)
class ClassificationPassSummary:
    id: int
    status: str
    classifier_version: str
    threshold: float
    eligible_count: int
    confident_count: int
    needs_review_count: int
    unknown_count: int
    changed_count: int
    labeled_example_count: int | None
    review_queue_size: int | None
    error_message: str | None
    started_at: datetime
    completed_at: datetime | None

    @classmethod
    def from_pass(
        cls, classification_pass: ClassificationPass
    ) -> ClassificationPassSummary:
        return cls(
            id=classification_pass.id,
            status=classification_pass.status.value,
            classifier_version=classification_pass.classifier_version,
            threshold=classification_pass.threshold,
            eligible_count=classification_pass.eligible_count,
            confident_count=classification_pass.confident_count,
            needs_review_count=classification_pass.needs_review_count,
            unknown_count=classification_pass.unknown_count,
            changed_count=classification_pass.changed_count,
            labeled_example_count=classification_pass.labeled_example_count,
            review_queue_size=classification_pass.review_queue_size,
            error_message=classification_pass.error_message,
            started_at=classification_pass.started_at,
            completed_at=classification_pass.completed_at,
        )


@dataclass(frozen=True)
class LearningMetrics:
    eligible_count: int
    reviewed_count: int
    labeled_example_count: int
    confident_count: int
    needs_review_count: int
    unknown_count: int
    coverage: float | None
    review_rate: float | None
    unknown_rate: float | None
    review_queue_size: int
    no_review_needed_count: int
    automation_rate: float | None
    last_reclassification: ClassificationPassSummary | None
    pass_history: list[ClassificationPassSummary]


class MetricsService:
    def __init__(
        self,
        session: Session,
        policy: ClassifierPolicy = DEFAULT_POLICY,
        history_limit: int = 10,
    ):
        self.session = session
        self.policy = policy
        self.history_limit = history_limit
        self.review_query = ReviewQueryService(session, policy=policy)

    def learning_metrics(self) -> LearningMetrics:
        eligible_count = self._count(
            select(func.count()).select_from(CropClassification)
        )

        reviewed_count = self.review_query.review_queue_stats().reviewed

        labeled_example_count = self._count(
            select(func.count()).select_from(EmbeddingExample)
        )

        unknown_count = self._count(
            select(func.count())
            .select_from(CropClassification)
            .where(CropClassification.identity.is_(None))
        )

        confident_count = self._count(
            select(func.count())
            .select_from(CropClassification)
            .where(
                CropClassification.identity.is_not(None),
                CropClassification.confidence >= self.policy.confident_threshold,
            )
        )

        needs_review_count = eligible_count - unknown_count - confident_count

        # The actual pending-work queue -- unreviewed items that are
        # unknown or below the confident threshold -- as opposed to
        # needs_review_count above, which (given the classifier never
        # assigns an identity below its own threshold) is populated almost
        # entirely by legacy/manual data rather than organic AUTO output.
        review_queue_size = self.review_query.review_queue_count()

        # "No review needed" is the complement of the queue: it answers
        # "how many images can I ignore right now," which includes both
        # confidently auto-classified items AND anything a human has
        # already reviewed (regardless of that item's confidence) -- not
        # only "how many did the classifier get right without help."
        no_review_needed_count = eligible_count - review_queue_size

        # SQLite's CURRENT_TIMESTAMP has only second-level resolution, so
        # started_at alone cannot break ties between passes created within
        # the same second -- id is a reliable secondary sort key since pass
        # ids are assigned in creation order.
        recent_passes = self.session.scalars(
            select(ClassificationPass)
            .order_by(
                ClassificationPass.started_at.desc(),
                ClassificationPass.id.desc(),
            )
            .limit(self.history_limit)
        ).all()

        pass_summaries = [
            ClassificationPassSummary.from_pass(classification_pass)
            for classification_pass in reversed(recent_passes)
        ]

        return LearningMetrics(
            eligible_count=eligible_count,
            reviewed_count=reviewed_count,
            labeled_example_count=labeled_example_count,
            confident_count=confident_count,
            needs_review_count=needs_review_count,
            unknown_count=unknown_count,
            coverage=(confident_count / eligible_count) if eligible_count else None,
            review_rate=(reviewed_count / eligible_count) if eligible_count else None,
            unknown_rate=(unknown_count / eligible_count) if eligible_count else None,
            review_queue_size=review_queue_size,
            no_review_needed_count=no_review_needed_count,
            automation_rate=(no_review_needed_count / eligible_count)
            if eligible_count
            else None,
            last_reclassification=pass_summaries[-1] if pass_summaries else None,
            pass_history=pass_summaries,
        )

    def _count(self, query) -> int:
        return self.session.scalar(query) or 0
