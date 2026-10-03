import logging
from pathlib import Path

from sqlalchemy import select
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


class ClassificationNotFoundError(ValueError):
    """
    The classification a correction targets does not exist. A distinct type so the API maps only
    this case to 404; any other failure while correcting (issue #362's embedding shape mismatch,
    for one) must surface as the server error it is, not as "not found".
    """


class NothingToUndoError(ValueError):
    """
    The classification's latest review action is not an identity correction, so there is nothing
    `undo_correction()` may reverse. A distinct type so the API maps it to 409.
    """


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
            raise ClassificationNotFoundError(
                f"Classification {classification_id} not found"
            )

        original_identity = classification.identity
        crop_path = Path(classification.crop.path) if self.learner is not None else None
        is_learnable = (
            self.learner is not None and identity is not None and identity != "Unknown"
        )

        # Run embedding inference (if any) before any write touches the
        # session below. This is a slow, CPU/GPU-bound step, and running it
        # after the classification/ReviewAction writes would hold state.db's
        # write lock -- taken as soon as those writes autoflush -- for
        # however long inference takes, blocking every other writer in the
        # app (e.g. creating a new pipeline job) until it either finishes or
        # exhausts the busy_timeout (issue #234). Nothing here has written
        # anything yet, so this only needs a read lock.
        learn_embedding = (
            self.learner.embedder.embed(crop_path) if is_learnable else None
        )

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
            if is_learnable:
                captured_at = None
                latitude = None
                longitude = None

                if (
                    classification.crop.detection is not None
                    and classification.crop.detection.asset is not None
                ):
                    asset = classification.crop.detection.asset
                    captured_at = asset.captured_at
                    latitude = asset.latitude
                    longitude = asset.longitude

                self.learner.learn_image(
                    identity,
                    crop_path,
                    species=classification.crop.species,
                    source=EmbeddingSources.REVIEW,
                    captured_at=captured_at,
                    latitude=latitude,
                    longitude=longitude,
                    embedding=learn_embedding,
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
            raise ClassificationNotFoundError(
                f"Classification {classification_id} not found"
            )

        crop = classification.crop
        original_species = crop.species

        if original_species == species:
            return classification

        original_identity = classification.identity
        crop_path = Path(crop.path)

        crop.species = species

        self._rescore(classification)

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

    def undo_correction(
        self,
        classification_id: int,
    ) -> CropClassification:
        """
        Reverse the latest identity correction, putting the item back in the
        review queue as if it had never been reviewed (issue #382).

        Only the single latest ReviewAction is removed, and only when it is a
        CORRECT: older history stays intact, and a skip is not this method's
        to reverse. The prediction is rescored rather than remembered, since
        it is derived state. The learning example the correction created is
        forgotten *before* rescoring so the crop can't match itself.
        """
        classification = self.session.get(
            CropClassification,
            classification_id,
        )

        if classification is None:
            raise ClassificationNotFoundError(
                f"Classification {classification_id} not found"
            )

        latest = self.session.scalar(
            select(ReviewAction)
            .where(ReviewAction.classification_id == classification_id)
            .order_by(ReviewAction.created_at.desc(), ReviewAction.id.desc())
            .limit(1)
        )

        if latest is None or latest.action != ReviewActions.CORRECT:
            raise NothingToUndoError(
                f"Classification {classification_id} has no correction to undo"
            )

        undone_identity = latest.identity
        self.session.delete(latest)

        if self.learner is not None:
            self.learner.forget_image(Path(classification.crop.path))
            self.session.flush()

        self._rescore(classification)
        classification.source = ClassificationSources.AUTO

        PetOccurrenceService(self.session).sync_classification(classification)

        self.session.commit()

        logger.info(
            "Classification %d correction undone: %r -> %r",
            classification.id,
            undone_identity,
            classification.identity,
        )

        return classification

    def _rescore(self, classification: CropClassification) -> None:
        """
        Recompute a classification's prediction from its stored embedding
        against its crop's current species pool. Shared by species
        correction and undo, which both need a fresh derived prediction
        rather than one remembered from before. Does not set `source`.
        """
        crop = classification.crop
        species = crop.species

        if classification.embedding is not None:
            embedding = blob_to_embedding(classification.embedding)

            captured_at = None
            latitude = None
            longitude = None

            if crop.detection is not None and crop.detection.asset is not None:
                asset = crop.detection.asset
                captured_at = asset.captured_at
                latitude = asset.latitude
                longitude = asset.longitude

            result = self.classifier.classify(
                embedding,
                species=species,
                captured_at=captured_at,
                latitude=latitude,
                longitude=longitude,
                embedding_model=classification.embedding_model,
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
                    "spatial_weight": candidate.spatial_weight,
                }
                for candidate in result.candidates
            ]
            classification.classifier_version = self.classifier.policy.version
        else:
            # No cached embedding to rescore against -- shouldn't happen for
            # a crop that reached the review queue (classify()/reclassify()
            # always store one), but fail open to Unknown rather than keep a
            # stale prediction.
            classification.identity = None
            classification.confidence = -1.0
            classification.matched_example_id = None
            classification.candidates = []
