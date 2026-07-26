from pathlib import Path

from sqlalchemy.orm import Session

from immich_dog_tagger.enums import ClassificationSources, EmbeddingSources
from immich_dog_tagger.models import (
    CropClassification,
)
from immich_dog_tagger.services.learner import Learner


class ClassificationCorrectionService:
    def __init__(
        self,
        session: Session,
        learner: Learner | None = None,
    ):
        self.session = session
        self.learner = learner

    def correct(
        self,
        classification_id: int,
        identity: str | None,
    ) -> CropClassification:
        classification = self.session.get(
            CropClassification,
            classification_id,
        )

        if classification is None:
            raise ValueError(f"Classification {classification_id} not found")

        classification.identity = identity
        classification.confidence = 1.0
        classification.source = ClassificationSources.REVIEW

        if self.learner is not None:
            self.learner.learn_image(
                identity,
                Path(classification.crop.path),
                source=EmbeddingSources.REVIEW,
            )

        self.session.commit()

        return classification
