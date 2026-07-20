from sqlalchemy.orm import Session
from dataclasses import dataclass
from pathlib import Path

from immich_dog_tagger.repository import get_crop_classifications


@dataclass(frozen=True)
class ReviewItem:
    classification_id: int
    crop_id: int
    identity: str | None
    confidence: float
    path: Path


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
        return get_crop_classifications(self.session)
