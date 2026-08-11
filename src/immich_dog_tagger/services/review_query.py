from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy import case, exists, func, select
from sqlalchemy.orm import Session, selectinload

from immich_dog_tagger.classifier import ClassificationCandidate
from immich_dog_tagger.models import (
    CropClassification,
    EmbeddingExample,
    ReviewAction,
)

# Eager-load the relationships _to_review_item() touches (crop, matched
# example, and the example's identity) so a review-queue page issues a
# constant number of queries instead of one extra round trip per row.
_REVIEW_ITEM_RELATIONSHIPS = (
    selectinload(CropClassification.crop),
    selectinload(CropClassification.matched_example).selectinload(
        EmbeddingExample.identity
    ),
)
from immich_dog_tagger.policy import (
    DEFAULT_POLICY,
    ClassificationDecision,
    ClassifierPolicy,
)


@dataclass(frozen=True)
class ReviewPrediction:
    identity: str | None
    similarity: float
    candidates: list[ClassificationCandidate]


@dataclass(frozen=True)
class ReviewSuggestion:
    identity: str
    similarity: float
    example_id: int
    example_path: Path
    captured_at: datetime | None


@dataclass(frozen=True)
class ReviewItem:
    classification_id: int
    crop_id: int
    path: Path
    prediction: ReviewPrediction
    suggestion: ReviewSuggestion | None
    reason: str = "review"

    @property
    def filename(self) -> str:
        return self.path.name


@dataclass(frozen=True)
class ReviewSummary:
    total: int
    identities: dict[str, int]
    unknown: int
    confidence_buckets: dict[str, int]


@dataclass(frozen=True)
class ReviewQueueStats:
    total: int
    reviewed: int
    remaining: int


class ReviewQueryService:
    def __init__(
        self,
        session: Session,
        policy: ClassifierPolicy = DEFAULT_POLICY,
    ):
        self.session = session
        self.policy = policy

    def classifications(
        self,
        *,
        limit: int | None = None,
        identity: str | None = None,
        unknown: bool = False,
        confidence_below: float | None = None,
    ) -> list[ReviewItem]:

        if unknown and identity is not None:
            raise ValueError("identity and unknown cannot be combined")

        query = (
            select(CropClassification)
            .options(*_REVIEW_ITEM_RELATIONSHIPS)
            .order_by(CropClassification.confidence.asc())
        )

        if unknown:
            query = query.where(CropClassification.identity.is_(None))

        if identity is not None:
            query = query.where(CropClassification.identity == identity)

        if confidence_below is not None:
            query = query.where(CropClassification.confidence < confidence_below)

        if limit is not None:
            query = query.limit(limit)

        classifications = self.session.scalars(query).all()

        return [
            self._to_review_item(classification) for classification in classifications
        ]

    def summary(self) -> ReviewSummary:
        query = select(CropClassification)

        classifications = self.session.scalars(query).all()

        total = len(classifications)

        identities = Counter()
        unknown = 0

        confidence_buckets = {
            "<0.80": 0,
            "0.80-0.90": 0,
            ">0.90": 0,
        }

        for classification in classifications:
            if classification.identity:
                identities[classification.identity] += 1
            else:
                unknown += 1

            if classification.confidence < 0.80:
                confidence_buckets["<0.80"] += 1
            elif classification.confidence < 0.90:
                confidence_buckets["0.80-0.90"] += 1
            else:
                confidence_buckets[">0.90"] += 1

        return ReviewSummary(
            total=total,
            identities=dict(identities),
            unknown=unknown,
            confidence_buckets=dict(confidence_buckets),
        )

    def review_queue_stats(self) -> ReviewQueueStats:
        total = self.session.scalar(
            select(func.count()).select_from(CropClassification)
        )

        reviewed = self.session.scalar(
            select(func.count())
            .select_from(CropClassification)
            .where(
                self._has_review_action(),
            )
        )

        return ReviewQueueStats(
            total=total or 0,
            reviewed=reviewed or 0,
            remaining=(total or 0) - (reviewed or 0),
        )

    def active_review(
        self,
        *,
        threshold: float | None = None,
        limit: int | None = None,
        unknown: bool = False,
        confidence_below: float | None = None,
        candidate_conflict: bool = False,
    ) -> list[ReviewItem]:
        threshold = (
            threshold if threshold is not None else self.policy.confident_threshold
        )

        priority = case(
            (
                CropClassification.identity.is_(None),
                0,
            ),
            else_=1,
        )

        query = (
            select(CropClassification)
            .options(*_REVIEW_ITEM_RELATIONSHIPS)
            .where(
                ~self._has_review_action(),
            )
            .where(
                (CropClassification.identity.is_(None))
                | (CropClassification.confidence < threshold)
            )
            .order_by(
                priority.asc(),
                CropClassification.confidence.asc(),
                CropClassification.created_at.asc(),
            )
        )

        if limit is not None:
            query = query.limit(limit)

        if unknown:
            query = query.where(CropClassification.identity.is_(None))

        if confidence_below is not None:
            query = query.where(CropClassification.confidence < confidence_below)

        if candidate_conflict:
            query = query.where(CropClassification.candidates != [])

        classifications = self.session.scalars(query).all()

        return [
            self._to_review_item(classification) for classification in classifications
        ]

    def _candidates(
        self,
        classification: CropClassification,
    ) -> list[ClassificationCandidate]:
        return [
            ClassificationCandidate(
                identity=candidate["identity"],
                similarity=candidate["similarity"],
                matched_example_id=candidate.get(
                    "matched_example_id",
                    -1,
                ),
            )
            for candidate in classification.candidates
        ]

    def _prediction(
        self,
        classification: CropClassification,
    ) -> ReviewPrediction:
        return ReviewPrediction(
            identity=classification.identity,
            similarity=classification.confidence,
            candidates=self._candidates(classification),
        )

    def _suggestion(
        self,
        classification: CropClassification,
    ) -> ReviewSuggestion | None:
        example = classification.matched_example

        if example is None:
            return None

        return ReviewSuggestion(
            identity=example.identity.name,
            similarity=classification.confidence,
            example_id=example.id,
            example_path=Path(example.crop_path),
            captured_at=example.captured_at,
        )

    def _to_review_item(
        self,
        classification: CropClassification,
    ) -> ReviewItem:
        return ReviewItem(
            classification_id=classification.id,
            crop_id=classification.crop.id,
            path=Path(classification.crop.path),
            prediction=self._prediction(classification),
            suggestion=self._suggestion(classification),
            reason=self._review_reason(classification),
        )

    def _has_review_action(self):
        return exists(
            select(ReviewAction.id).where(
                ReviewAction.classification_id == CropClassification.id,
            )
        )

    def _review_reason(
        self,
        classification: CropClassification,
    ) -> str:
        decision = self.policy.decide(
            identity=classification.identity,
            similarity=classification.confidence,
        )

        if decision is ClassificationDecision.UNKNOWN:
            return "unknown"

        if classification.candidates:
            return "candidate-conflict"

        if decision is ClassificationDecision.NEEDS_REVIEW:
            return "low-confidence"

        return "review"
