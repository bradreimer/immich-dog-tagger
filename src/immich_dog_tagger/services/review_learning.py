from pathlib import Path

from immich_dog_tagger.enums import EmbeddingSources
from immich_dog_tagger.models import CropClassification
from immich_dog_tagger.services.learner import Learner


class ReviewLearningService:
    def __init__(
        self,
        learner: Learner,
    ):
        self.learner = learner

    def learn_from_correction(
        self,
        classification: CropClassification,
        identity: str,
    ) -> None:
        captured_at = None

        if (
            classification.crop.detection is not None
            and classification.crop.detection.asset is not None
        ):
            captured_at = classification.crop.detection.asset.captured_at

        self.learner.learn_image(
            identity,
            Path(classification.crop.path),
            source=EmbeddingSources.REVIEW,
            captured_at=captured_at,
        )
