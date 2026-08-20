"""
"Not this pet" -- the negative review signal (issue #144).
"""

import numpy as np
from sqlalchemy.orm import Session

from immich_dog_tagger.classifier import IdentityClassifier
from immich_dog_tagger.embeddings import embedding_to_blob
from immich_dog_tagger.enums import (
    ClassificationSources,
    EmbeddingSources,
    Species,
)
from immich_dog_tagger.models import (
    Crop,
    CropClassification,
    CropIdentityRejection,
    EmbeddingExample,
    Identity,
)
from immich_dog_tagger.services.rejections import (
    RejectionService,
    rejected_identities_for,
)
from immich_dog_tagger.services.review_query import ReviewQueryService


class FakeLearner:
    """Records forget_image calls; the real Learner needs an embedder."""

    def __init__(self, session):
        self.session = session
        self.forgotten = []

    def forget_image(self, image_path):
        self.forgotten.append(str(image_path))

        examples = (
            self.session.query(EmbeddingExample)
            .filter(EmbeddingExample.crop_path == str(image_path))
            .all()
        )

        for example in examples:
            self.session.delete(example)

        return len(examples)


# Far enough from Fibs' reference that a crop matching Fibs scores below
# the confident threshold against Hermann -- so rejecting Fibs leaves the
# crop unsettled, which is the case most of these tests are about.
DISTINCT_SECOND = np.array([0.0, 1.0, 0.0])

# Close enough that rejecting one hands a confident match to the other.
LOOKALIKE_SECOND = np.array([0.96, 0.28, 0.0])


def _seed_two_pets(
    session: Session,
    *,
    species: Species = Species.DOG,
    second_embedding=DISTINCT_SECOND,
):
    """Two identities, each with one reference example a crop can match."""
    first = Identity(name="Fibs", species=species, is_active=True)
    second = Identity(name="Hermann", species=species, is_active=True)

    session.add_all([first, second])
    session.flush()

    session.add_all(
        [
            EmbeddingExample(
                identity_id=first.id,
                crop_path="fibs-reference.jpg",
                embedding=embedding_to_blob(np.array([1.0, 0.0, 0.0])),
                source=EmbeddingSources.REVIEW,
            ),
            EmbeddingExample(
                identity_id=second.id,
                crop_path="hermann-reference.jpg",
                embedding=embedding_to_blob(second_embedding),
                source=EmbeddingSources.REVIEW,
            ),
        ]
    )
    session.flush()

    return first, second


def _seed_crop(
    session: Session,
    *,
    embedding=None,
    species: Species = Species.DOG,
    path: str = "crop.jpg",
) -> CropClassification:
    crop = Crop(detection_id=1, path=path, species=species)
    session.add(crop)
    session.flush()

    classification = CropClassification(
        crop=crop,
        identity=None,
        confidence=0.5,
        embedding=(embedding_to_blob(embedding) if embedding is not None else None),
    )

    session.add(classification)
    session.commit()

    return classification


def test_rejection_records_the_fact_without_assigning_an_identity(engine):
    with Session(engine) as session:
        _seed_two_pets(session)
        classification = _seed_crop(session, embedding=np.array([1.0, 0.0, 0.0]))

        RejectionService(session).reject(classification.id, "Fibs")

        rejections = session.query(CropIdentityRejection).all()

        assert len(rejections) == 1
        assert rejections[0].identity == "Fibs"
        assert rejections[0].crop_id == classification.crop_id

        # It said who this is not, not who it is.
        assert classification.identity != "Fibs"


def test_rejection_writes_no_review_action_and_leaves_the_crop_unreviewed(engine):
    """
    The reason this is its own table: every count that derives from a
    ReviewAction existing must be unmoved by a rejection, or a crop whose
    identity is still unsettled starts reporting as reviewed.
    """
    with Session(engine) as session:
        _seed_two_pets(session)
        classification = _seed_crop(session, embedding=np.array([1.0, 0.0, 0.0]))

        query = ReviewQueryService(session)
        queue_before = query.review_queue_count()

        RejectionService(session).reject(classification.id, "Fibs")

        assert classification.review_actions == []

        # Rejecting Fibs left no confident alternative, so the crop is still
        # waiting on a human -- it must not have been counted as reviewed
        # and dropped out of the queue.
        assert classification.identity is None
        assert query.review_queue_count() == queue_before

        entry = next(
            item
            for item in query.library().items
            if item.item.classification_id == classification.id
        )

        assert entry.reviewed is False


def test_rejection_rescores_to_the_next_best_candidate(engine):
    """
    The owner supplied real information, so the useful answer is the
    next-best candidate rather than an emptied field.
    """
    with Session(engine) as session:
        _seed_two_pets(
            session,
            second_embedding=LOOKALIKE_SECOND,
        )
        classification = _seed_crop(session, embedding=np.array([1.0, 0.0, 0.0]))

        # Closest to Fibs' reference, so that is what it lands on first.
        RejectionService(session).reject(classification.id, "Hermann")
        assert classification.identity == "Fibs"

        RejectionService(session).reject(classification.id, "Fibs")

        # Both rejected: nothing left to propose, and crucially not a
        # manufactured confidence for an identity the owner ruled out.
        assert classification.identity is None
        assert classification.candidates == []


def test_rejected_identity_is_suppressed_from_candidates_too(engine):
    """
    Not just the accepted identity: a rejected pet must not come back as a
    runner-up either, or it reappears in the next cluster proposal.
    """
    with Session(engine) as session:
        _seed_two_pets(session)
        classification = _seed_crop(session, embedding=np.array([1.0, 0.0, 0.0]))

        RejectionService(session).reject(classification.id, "Fibs")

        assert all(
            candidate["identity"] != "Fibs" for candidate in classification.candidates
        )


def test_rejection_survives_reclassification(engine):
    """
    A rejection is human input, so a later derived pass must not undo it.
    """
    with Session(engine) as session:
        _seed_two_pets(session)
        classification = _seed_crop(session, embedding=np.array([1.0, 0.0, 0.0]))

        RejectionService(session).reject(classification.id, "Fibs")

        # Reclassify's own path: the classifier, given this crop's
        # rejections, must not re-propose the rejected pet.
        rejections = rejected_identities_for(session, [classification.crop_id])

        result = IdentityClassifier(session).classify(
            np.array([1.0, 0.0, 0.0]),
            species=Species.DOG,
            excluded_identities=rejections.get(classification.crop_id),
        )

        assert result.identity != "Fibs"
        assert all(candidate.identity != "Fibs" for candidate in result.candidates)


def test_rejection_forgets_a_reference_example_learned_as_that_pet(engine):
    """
    If the crop had been learned as the rejected pet, that example is now
    known to be wrong and must stop teaching the mistake.
    """
    with Session(engine) as session:
        fibs, _ = _seed_two_pets(session)
        classification = _seed_crop(
            session,
            embedding=np.array([1.0, 0.0, 0.0]),
            path="learned-crop.jpg",
        )

        session.add(
            EmbeddingExample(
                identity_id=fibs.id,
                crop_path="learned-crop.jpg",
                embedding=embedding_to_blob(np.array([1.0, 0.0, 0.0])),
                source=EmbeddingSources.REVIEW,
            )
        )
        session.commit()

        learner = FakeLearner(session)

        RejectionService(session, learner=learner).reject(
            classification.id,
            "Fibs",
        )

        assert learner.forgotten == ["learned-crop.jpg"]

        remaining = (
            session.query(EmbeddingExample)
            .filter(EmbeddingExample.crop_path == "learned-crop.jpg")
            .all()
        )

        assert remaining == []


def test_rejection_keeps_an_example_learned_as_a_different_pet(engine):
    with Session(engine) as session:
        fibs, _ = _seed_two_pets(session)
        classification = _seed_crop(
            session,
            embedding=np.array([1.0, 0.0, 0.0]),
            path="learned-crop.jpg",
        )

        session.add(
            EmbeddingExample(
                identity_id=fibs.id,
                crop_path="learned-crop.jpg",
                embedding=embedding_to_blob(np.array([1.0, 0.0, 0.0])),
                source=EmbeddingSources.REVIEW,
            )
        )
        session.commit()

        learner = FakeLearner(session)

        # Rejecting the *other* pet says nothing about the Fibs example.
        RejectionService(session, learner=learner).reject(
            classification.id,
            "Hermann",
        )

        assert learner.forgotten == []


def test_rejecting_twice_records_one_fact(engine):
    with Session(engine) as session:
        _seed_two_pets(session)
        classification = _seed_crop(session, embedding=np.array([1.0, 0.0, 0.0]))

        service = RejectionService(session)
        service.reject(classification.id, "Fibs")
        service.reject(classification.id, "Fibs")

        assert session.query(CropIdentityRejection).count() == 1


def test_rejecting_an_unknown_pet_is_refused(engine):
    with Session(engine) as session:
        _seed_two_pets(session)
        classification = _seed_crop(session, embedding=np.array([1.0, 0.0, 0.0]))

        try:
            RejectionService(session).reject(classification.id, "Nobody")
        except ValueError as error:
            assert "Nobody" in str(error)
        else:
            raise AssertionError("expected a ValueError")

        assert session.query(CropIdentityRejection).count() == 0


def test_rejecting_a_pet_of_another_species_is_refused(engine):
    """
    Names are unique only per species (DT-1110), so a bare name is
    ambiguous without the species check.
    """
    with Session(engine) as session:
        _seed_two_pets(session, species=Species.DOG)

        cat = Identity(name="Whiskers", species=Species.CAT, is_active=True)
        session.add(cat)
        session.flush()

        classification = _seed_crop(
            session,
            embedding=np.array([1.0, 0.0, 0.0]),
            species=Species.DOG,
        )

        try:
            RejectionService(session).reject(classification.id, "Whiskers")
        except ValueError:
            pass
        else:
            raise AssertionError("expected a ValueError")

        assert session.query(CropIdentityRejection).count() == 0


def test_rejection_without_a_stored_embedding_fails_open_to_unknown(engine):
    with Session(engine) as session:
        _seed_two_pets(session)
        classification = _seed_crop(session, embedding=None)
        classification.identity = "Fibs"
        classification.confidence = 0.91
        session.commit()

        RejectionService(session).reject(classification.id, "Fibs")

        assert classification.identity is None
        assert classification.candidates == []
        assert classification.source == ClassificationSources.AUTO


def test_rejected_identities_for_bulk_loads_in_one_query(engine):
    with Session(engine) as session:
        _seed_two_pets(session)

        first = _seed_crop(session, embedding=np.array([1.0, 0.0, 0.0]), path="a.jpg")
        second = _seed_crop(session, embedding=np.array([1.0, 0.0, 0.0]), path="b.jpg")

        service = RejectionService(session)
        service.reject(first.id, "Fibs")
        service.reject(second.id, "Hermann")

        rejections = rejected_identities_for(
            session,
            [first.crop_id, second.crop_id],
        )

        assert rejections[first.crop_id] == {"Fibs"}
        assert rejections[second.crop_id] == {"Hermann"}


def test_rejected_identities_for_empty_input_makes_no_query(engine):
    with Session(engine) as session:
        assert rejected_identities_for(session, []) == {}
