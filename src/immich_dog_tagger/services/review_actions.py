from sqlalchemy import select
from sqlalchemy.orm import Session

from immich_dog_tagger.enums import ReviewActions
from immich_dog_tagger.models import CropClassification, ReviewAction


class ReviewActionService:
    def __init__(
        self,
        session: Session,
    ):
        self.session = session

    def skip(
        self,
        classification_id: int,
    ) -> None:
        classification = self.session.get(
            CropClassification,
            classification_id,
        )

        if classification is None:
            raise ValueError(f"Classification {classification_id} not found")

        existing_skip = self.session.scalar(
            select(ReviewAction).where(
                ReviewAction.classification_id == classification.id,
                ReviewAction.action == ReviewActions.SKIP,
            )
        )

        if existing_skip is None:
            self.session.add(
                ReviewAction(
                    classification_id=classification.id,
                    action=ReviewActions.SKIP,
                )
            )

        self.session.commit()
