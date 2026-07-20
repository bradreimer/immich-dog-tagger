from dataclasses import dataclass
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


class ReviewService:
    def __init__(
        self,
        session: Session,
    ):
        self.session = session

    def classifications(
        self,
        limit: int | None = None,
        identity: str | None = None,
    ) -> list[ReviewItem]:
        query = select(CropClassification).order_by(CropClassification.confidence.asc())

        if identity is not None:
            query = query.where(CropClassification.identity == identity)

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
