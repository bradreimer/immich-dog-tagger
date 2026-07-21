from dataclasses import dataclass
from collections import Counter
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from immich_dog_tagger.models import CropClassification


@dataclass(frozen=True)
class ReviewItem:
    classification_id: int
    crop_id: int
    identity: str | None
    confidence: float
    path: Path

    @property
    def filename(self) -> str:
        return self.path.name


@dataclass(frozen=True)
class ReviewSummary:
    total: int
    identities: dict[str, int]
    unknown: int
    confidence_buckets: dict[str, int]


class ReviewService:
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
            ReviewItem(
                classification_id=classification.id,
                crop_id=classification.crop.id,
                identity=classification.identity,
                confidence=classification.confidence,
                path=Path(classification.crop.path),
            )
            for classification in classifications
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

    def active_review(
        self,
        *,
        threshold: float = 0.80,
        limit: int | None = None,
    ) -> list[ReviewItem]:
        query = (
            select(CropClassification)
            .where(
                (CropClassification.identity.is_(None))
                | (CropClassification.confidence < threshold)
            )
            .order_by(CropClassification.confidence.asc())
        )

        if limit is not None:
            query = query.limit(limit)

        classifications = self.session.scalars(query).all()

        return [
            ReviewItem(
                classification_id=classification.id,
                crop_id=classification.crop.id,
                identity=classification.identity,
                confidence=classification.confidence,
                path=Path(classification.crop.path),
            )
            for classification in classifications
        ]
