import logging
from pathlib import Path

from sqlalchemy.orm import Session

from immich_dog_tagger.classifier import IdentityClassifier
from immich_dog_tagger.embeddings import blob_to_embedding
from immich_dog_tagger.enums import (
    ClassificationSources,
    EmbeddingSources,
    ReviewActions,
    Species,
)
from immich_dog_tagger.models import (
    CropClassification,
    ReviewAction,
)
from immich_dog_tagger.services.learner import Learner
from immich_dog_tagger.services.pet_occurrences import PetOccurrenceService

logger = logging.getLogger(__name__)


class ClassificationCorrectionService:
    def __init__(
        self,
        session: Session,
        learner: Learner | None = None,
        classifier: IdentityClassifier | None = None,
    ):
        self.session = session
        self.learner = learner
        self.classifier = classifier or IdentityClassifier(session)

    def correct(
        self,
        classification_id: int,
        identity: str | None,
        *,
        commit: bool = True,
    ) -> CropClassification:
        """
        Settle one classification's identity as a human decision.

        `commit=False` leaves the write to the caller so a bulk caller
        (cluster approval, issue #141) can checkpoint several corrections
        per transaction instead of taking state.db's write lock once per
        photo. It changes nothing else: the ReviewAction, the reference
        example, and the provenance are identical either way.
        """
        classification = self.session.get(
            CropClassification,
            classification_id,
        )

        if classification is None:
            raise ValueError(f"Classification {classification_id} not found")

        original_identity = classification.identity

        self.session.add(
            ReviewAction(
                classification_id=classification.id,
                action=ReviewActions.CORRECT,
                original_identity=original_identity,
                identity=identity,
            )
        )

        classification.identity = identity
        classification.confidence = 1.0
        classification.source = ClassificationSources.REVIEW

        PetOccurrenceService(self.session).sync_classification(classification)

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
                    species=classification.crop.species,
                    source=EmbeddingSources.REVIEW,
                    captured_at=captured_at,
                )
            else:
                # Corrected to Unknown: this crop should no longer serve as a
                # reference example for whatever identity it was previously
                # attributed to.
                self.learner.forget_image(crop_path)

        if commit:
            self.session.commit()

        logger.info(
            "Classification %d corrected: %r -> %r",
            classification.id,
            original_identity,
            identity,
        )

        return classification

    def correct_species(
        self,
        classification_id: int,
        species: Species,
    ) -> CropClassification:
        """
        Fix a crop whose species was misdetected (e.g. a cat cropped as a
        dog). Unlike correct(), this does not decide an identity, so it must
        never write a ReviewAction: doing so would make
        ReviewQueryService.review_queue_count() treat the item as already
        reviewed and drop it from the active queue while it's still
        effectively unclassified, waiting on a human to pick an identity
        under the corrected species.
        """
        classification = self.session.get(
            CropClassification,
            classification_id,
        )

        if classification is None:
            raise ValueError(f"Classification {classification_id} not found")

        crop = classification.crop
        original_species = crop.species

        if original_species == species:
            return classification

        original_identity = classification.identity
        crop_path = Path(crop.path)

        crop.species = species

        if classification.embedding is not None:
            embedding = blob_to_embedding(classification.embedding)

            captured_at = None

            if crop.detection is not None and crop.detection.asset is not None:
                captured_at = crop.detection.asset.captured_at

            result = self.classifier.classify(
                embedding,
                species=species,
                captured_at=captured_at,
            )

            classification.identity = result.identity
            classification.confidence = result.similarity
            classification.matched_example_id = result.matched_example_id
            classification.candidates = [
                {
                    "identity": candidate.identity,
                    "similarity": candidate.similarity,
                    "matched_example_id": candidate.matched_example_id,
                    "temporal_weight": candidate.temporal_weight,
                }
                for candidate in result.candidates
            ]
            classification.classifier_version = self.classifier.policy.version
        else:
            # No cached embedding to rescore against -- shouldn't happen for
            # a crop that reached the review queue (classify()/reclassify()
            # always store one), but fail open to Unknown rather than keep a
            # prediction computed under the wrong species.
            classification.identity = None
            classification.confidence = -1.0
            classification.matched_example_id = None
            classification.candidates = []

        classification.source = ClassificationSources.AUTO

        PetOccurrenceService(self.session).sync_classification(classification)

        if self.learner is not None and original_identity is not None:
            # The crop's whole species assignment was wrong, so any example
            # learned from it belongs to the wrong species' identity too.
            self.learner.forget_image(crop_path)

        self.session.commit()

        logger.info(
            "Classification %d species corrected: %r -> %r (identity %r -> %r)",
            classification.id,
            original_species,
            species,
            original_identity,
            classification.identity,
        )

        return classification
