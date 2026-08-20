"""
"Not this pet" -- the negative review signal (issue #144).

Until now the app had two review actions, CORRECT and SKIP, and "Unknown"
was an identity *assignment* rather than a rejection. So an owner looking at
a recommendation they knew was wrong could only skip it (and see it again
next pass) or name the right pet (which they may not know). Every comparable
faces workflow captures the negative -- Apple's "X is Not in This Photo",
Immich's detach-a-face -- and for visually similar pets it is the cheapest
separating signal there is.

Two properties make this safe to add to a system whose whole premise is that
human input is ground truth:

- A rejection **does not settle the crop**. It says who the animal is not,
  leaving "who is it?" open, so the crop stays in the review queue and is
  not counted as reviewed. That is why it is stored in its own table rather
  than as a `ReviewActions` value -- see `CropIdentityRejection`.
- A rejection **outranks derived state**. It is human input, so
  reclassification must never re-propose the rejected identity; the
  suppression lives in `IdentityClassifier.classify()`, the one place that
  owns the nearest-neighbour decision.
"""

import logging
from collections.abc import Iterable
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from immich_dog_tagger.classifier import IdentityClassifier
from immich_dog_tagger.embeddings import blob_to_embedding
from immich_dog_tagger.enums import ClassificationSources
from immich_dog_tagger.models import (
    CropClassification,
    CropIdentityRejection,
    EmbeddingExample,
    Identity,
)
from immich_dog_tagger.services.learner import Learner
from immich_dog_tagger.services.pet_occurrences import PetOccurrenceService

logger = logging.getLogger(__name__)


def rejected_identities_for(
    session: Session,
    crop_ids: Iterable[int],
) -> dict[int, set[str]]:
    """
    Rejections for many crops in one query, keyed by crop id.

    Bulk by design: the pipeline's classify stage and Reclassify both apply
    suppression per crop across a whole batch, and doing that with a query
    per crop is the N+1 shape DT-1008 and #1111 already had to fix twice.
    """
    ids = list(crop_ids)

    if not ids:
        return {}

    rows = session.execute(
        select(
            CropIdentityRejection.crop_id,
            CropIdentityRejection.identity,
        ).where(CropIdentityRejection.crop_id.in_(ids))
    ).all()

    rejections: dict[int, set[str]] = {}

    for crop_id, identity in rows:
        rejections.setdefault(crop_id, set()).add(identity)

    return rejections


class RejectionService:
    def __init__(
        self,
        session: Session,
        learner: Learner | None = None,
        classifier: IdentityClassifier | None = None,
    ):
        self.session = session
        self.learner = learner
        self.classifier = classifier or IdentityClassifier(session)

    def reject(
        self,
        classification_id: int,
        identity: str,
        *,
        commit: bool = True,
    ) -> CropClassification:
        """
        Record that this crop is not `identity`, and rescore it without that
        pet in the running.

        Rescoring rather than blanking the prediction is deliberate: the
        owner has just supplied real information, and the useful response is
        the next-best candidate, not an empty field. It reuses the crop's
        stored embedding, so this costs no re-embedding -- the same approach
        `correct_species()` takes.

        `commit=False` lets a bulk caller (rejecting a selection from a
        cluster) checkpoint several rejections per transaction rather than
        taking state.db's write lock once per photo.
        """
        classification = self.session.get(CropClassification, classification_id)

        if classification is None:
            raise ValueError(f"Classification {classification_id} not found")

        crop = classification.crop
        species = crop.species

        # A rejection names a real pet of the crop's own species. Rejecting
        # a name that is not an identity, or a dog's name for a cat crop,
        # is a bug in the caller rather than a fact worth storing -- and
        # names are unique only per species (DT-1110), so the species check
        # is what makes the name unambiguous.
        identity_row = self.session.scalars(
            select(Identity).where(
                Identity.name == identity,
                Identity.species == species,
            )
        ).one_or_none()

        if identity_row is None:
            raise ValueError(f"No {species.value} identity named {identity!r}")

        already_rejected = self.session.scalars(
            select(CropIdentityRejection).where(
                CropIdentityRejection.crop_id == crop.id,
                CropIdentityRejection.identity == identity,
            )
        ).one_or_none()

        if already_rejected is None:
            self.session.add(
                CropIdentityRejection(
                    crop_id=crop.id,
                    identity=identity,
                )
            )
            # Visible to the rescore below, which reads rejections back
            # through the same session.
            self.session.flush()

        if self.learner is not None:
            # If this crop was previously learned as the rejected pet, that
            # reference example is now known to be wrong, and leaving it in
            # place would keep teaching the mistake to every later
            # classification. Same remedy `correct_species()` applies to an
            # example filed under the wrong species.
            self._forget_if_learned_as(crop, identity)

        self._rescore(classification)

        if commit:
            self.session.commit()

        logger.info(
            "Crop %d rejected as %r; rescored to %r",
            crop.id,
            identity,
            classification.identity,
        )

        return classification

    def rejected_identities(self, crop_id: int) -> set[str]:
        return rejected_identities_for(self.session, [crop_id]).get(crop_id, set())

    def _forget_if_learned_as(self, crop, identity: str) -> None:
        learned_as_rejected = self.session.scalars(
            select(EmbeddingExample)
            .join(Identity)
            .where(
                EmbeddingExample.crop_path == str(crop.path),
                Identity.name == identity,
                Identity.species == crop.species,
            )
        ).first()

        if learned_as_rejected is not None:
            self.learner.forget_image(Path(crop.path))

    def _rescore(self, classification: CropClassification) -> None:
        """
        Recompute this crop's prediction with every rejected identity
        excluded, from the embedding already stored on the row.
        """
        crop = classification.crop
        excluded = self.rejected_identities(crop.id)

        if classification.embedding is None:
            # No cached embedding to rescore against. Fail open to Unknown
            # rather than leave a prediction standing that the owner has
            # just told us is wrong -- the same choice `correct_species()`
            # makes for this case.
            classification.identity = None
            classification.confidence = -1.0
            classification.matched_example_id = None
            classification.candidates = []
            classification.source = ClassificationSources.AUTO

            PetOccurrenceService(self.session).sync_classification(classification)
            return

        captured_at = None

        if crop.detection is not None and crop.detection.asset is not None:
            captured_at = crop.detection.asset.captured_at

        result = self.classifier.classify(
            blob_to_embedding(classification.embedding),
            species=crop.species,
            captured_at=captured_at,
            excluded_identities=excluded,
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
        # Still a derived prediction: the human said who this is *not*, not
        # who it is, so the crop stays AUTO and stays in the review queue.
        classification.source = ClassificationSources.AUTO

        PetOccurrenceService(self.session).sync_classification(classification)
