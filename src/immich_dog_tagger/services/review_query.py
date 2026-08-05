from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy import case, exists, func, select
from sqlalchemy.orm import Session

from immich_dog_tagger.models import (
    CropClassification,
    ReviewAction,
)


@dataclass(frozen=True)
class ReviewPrediction:
    identity: str | None
    similarity: float
    candidates: list[dict]


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
    ):
        self.session = session

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

        query = select(CropClassification).order_by(CropClassification.confidence.asc())

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
        threshold: float = 0.80,
        limit: int | None = None,
        unknown: bool = False,
        confidence_below: float | None = None,
    ) -> list[ReviewItem]:
        priority = case(
            (
                CropClassification.identity.is_(None),
                0,
            ),
            else_=1,
        )

        query = (
            select(CropClassification)
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

        classifications = self.session.scalars(query).all()

        return [
            self._to_review_item(classification) for classification in classifications
        ]

    def _prediction(
        self,
        classification: CropClassification,
    ) -> ReviewPrediction:
        return ReviewPrediction(
            identity=classification.identity,
            similarity=classification.confidence,
            candidates=classification.candidates,
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
        threshold: float = 0.80,
    ) -> str:
        if classification.identity is None:
            return "unknown"

        if classification.confidence < threshold:
            return "low-confidence"

        return "review"
