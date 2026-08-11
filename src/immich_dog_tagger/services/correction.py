from pathlib import Path

from sqlalchemy.orm import Session

from immich_dog_tagger.enums import (
    ClassificationSources,
    EmbeddingSources,
    ReviewActions,
)
from immich_dog_tagger.models import (
    CropClassification,
    ReviewAction,
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

        self.session.add(
            ReviewAction(
                classification_id=classification.id,
                action=ReviewActions.CORRECT,
                original_identity=classification.identity,
                identity=identity,
            )
        )

        classification.identity = identity
        classification.confidence = 1.0
        classification.source = ClassificationSources.REVIEW

        if self.learner is not None:
            crop_path = Path(classification.crop.path)

            if identity is not None and identity != "Unknown":
                captured_at = None

                if (
                    classification.crop.detection is not None
                    and classification.crop.detection.asset is not None
                ):
                    captured_at = classification.crop.detection.asset.captured_at

                self.learner.learn_image(
                    identity,
                    crop_path,
                    source=EmbeddingSources.REVIEW,
                    captured_at=captured_at,
                )
            else:
                # Corrected to Unknown: this crop should no longer serve as a
                # reference example for whatever identity it was previously
                # attributed to.
                self.learner.forget_image(crop_path)

        self.session.commit()

        return classification
