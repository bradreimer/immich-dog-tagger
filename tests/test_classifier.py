from datetime import UTC, datetime

import numpy as np
from sqlalchemy.orm import Session

from immich_dog_tagger.classifier import IdentityClassifier
from immich_dog_tagger.embeddings import embedding_to_blob
from immich_dog_tagger.enums import ClassificationMode, Species
from immich_dog_tagger.models import (
    EmbeddingExample,
    EmbeddingSources,
    Identity,
)
from immich_dog_tagger.services.classification import ClassificationService


def _naive(*args) -> datetime:
    return datetime(*args, tzinfo=UTC).replace(tzinfo=None)


def test_classifier_finds_closest_identity(engine):
    with Session(engine) as session:
        hermann = Identity(name="Hermann")

        session.add(hermann)
        session.flush()

        example = EmbeddingExample(
            identity_id=hermann.id,
            crop_path="hermann.jpg",
            embedding=embedding_to_blob(
                np.array(
                    [1, 0, 0],
                    dtype=np.float32,
                )
            ),
            source=EmbeddingSources.BOOTSTRAP,
        )

        session.add(example)
        session.commit()

        classifier = IdentityClassifier(session)

        result = classifier.classify(
            np.array(
                [0.9, 0.1, 0],
                dtype=np.float32,
            )
        )

        assert result.identity == "Hermann"
        assert result.similarity > 0.9
        assert result.matched_example_id == example.id


def test_classifier_selects_best_matching_example(engine):
    with Session(engine) as session:
        fibs = Identity(name="Fibs")
        hermann = Identity(name="Hermann")

        session.add_all(
            [
                fibs,
                hermann,
            ]
        )
        session.flush()

        session.add_all(
            [
                EmbeddingExample(
                    identity_id=fibs.id,
                    crop_path="fibs.jpg",
                    embedding=embedding_to_blob(
                        np.array(
                            [1, 0, 0],
                            dtype=np.float32,
                        )
                    ),
                    source=EmbeddingSources.BOOTSTRAP,
                ),
                EmbeddingExample(
                    identity_id=hermann.id,
                    crop_path="hermann.jpg",
                    embedding=embedding_to_blob(
                        np.array(
                            [0, 1, 0],
                            dtype=np.float32,
                        )
                    ),
                    source=EmbeddingSources.BOOTSTRAP,
                ),
            ]
        )

        session.commit()

        classifier = IdentityClassifier(session)

        result = classifier.classify(
            np.array(
                [0.9, 0.1, 0],
                dtype=np.float32,
            )
        )

        assert result.identity == "Fibs"
        assert len(result.candidates) == 2
        assert result.candidates[0].identity == "Fibs"
        assert result.candidates[0].similarity > result.candidates[1].similarity


def test_classifier_never_returns_cross_species_candidate(engine):
    # DT-1110 acceptance criterion 3: a cat crop is never suggested a dog
    # identity, and vice versa. Both identities have the *same* name and
    # the *identical* embedding -- the strongest possible case, since
    # without species scoping this would be an exact match either way.
    with Session(engine) as session:
        dog_max = Identity(name="Max", species=Species.DOG)
        cat_max = Identity(name="Max", species=Species.CAT)

        session.add_all([dog_max, cat_max])
        session.flush()

        shared_embedding = embedding_to_blob(np.array([1, 0, 0], dtype=np.float32))

        session.add_all(
            [
                EmbeddingExample(
                    identity_id=dog_max.id,
                    crop_path="dog-max.jpg",
                    embedding=shared_embedding,
                    source=EmbeddingSources.BOOTSTRAP,
                ),
                EmbeddingExample(
                    identity_id=cat_max.id,
                    crop_path="cat-max.jpg",
                    embedding=shared_embedding,
                    source=EmbeddingSources.BOOTSTRAP,
                ),
            ]
        )
        session.commit()

        # One classifier instance, reused for both species -- reclassify
        # shares exactly one instance across a mixed-species batch, so the
        # per-species partition inside _load_examples must hold up here.
        classifier = IdentityClassifier(session)
        probe = np.array([1, 0, 0], dtype=np.float32)

        dog_result = classifier.classify(probe, species=Species.DOG)
        cat_result = classifier.classify(probe, species=Species.CAT)

        assert dog_result.identity == "Max"
        assert dog_result.matched_example_id != cat_result.matched_example_id
        assert len(dog_result.candidates) == 1

        assert cat_result.identity == "Max"
        assert len(cat_result.candidates) == 1

        # No unrequested species (e.g. a bird identity, if one existed)
        # ever leaks into either result.
        assert {c.matched_example_id for c in dog_result.candidates} != {
            c.matched_example_id for c in cat_result.candidates
        }


def test_classifier_prefers_temporally_closer_identity_when_visually_tied(engine):
    """v1.5/ADR-003: two identities with identical-looking embeddings (e.g.
    a pet that has passed away and a new, visually similar pet) must be
    disambiguated by which one's own reference examples are closer in time
    to the photo being classified -- automatically, using only each
    identity's own photo history."""
    with Session(engine) as session:
        old_dog = Identity(name="OldDog")
        new_dog = Identity(name="NewDog")

        session.add_all([old_dog, new_dog])
        session.flush()

        shared_embedding = embedding_to_blob(np.array([1, 0, 0], dtype=np.float32))

        session.add_all(
            [
                EmbeddingExample(
                    identity_id=old_dog.id,
                    crop_path="old.jpg",
                    embedding=shared_embedding,
                    source=EmbeddingSources.BOOTSTRAP,
                    captured_at=_naive(2015, 6, 1),
                ),
                EmbeddingExample(
                    identity_id=new_dog.id,
                    crop_path="new.jpg",
                    embedding=shared_embedding,
                    source=EmbeddingSources.BOOTSTRAP,
                    captured_at=_naive(2026, 5, 1),
                ),
            ]
        )
        session.commit()

        classifier = IdentityClassifier(session)
        probe = np.array([1, 0, 0], dtype=np.float32)

        # A recent photo favors NewDog, whose examples are close in time.
        recent_result = classifier.classify(
            probe,
            captured_at=_naive(2026, 6, 1),
        )
        assert recent_result.identity == "NewDog"

        # The exact same probe and reference examples, but an old photo,
        # correctly favors OldDog instead.
        old_result = classifier.classify(
            probe,
            captured_at=_naive(2015, 7, 1),
        )
        assert old_result.identity == "OldDog"


def test_classifier_single_identity_confidence_unaffected_by_temporal_distance(
    engine,
):
    """A lone identity's only known example being from years earlier must
    not, by itself, demote an otherwise-confident match to needs-review --
    there is no competing identity to disambiguate against yet, so the
    reported confidence stays the example's true raw similarity."""
    with Session(engine) as session:
        fibs = Identity(name="Fibs")

        session.add(fibs)
        session.flush()

        session.add(
            EmbeddingExample(
                identity_id=fibs.id,
                crop_path="fibs.jpg",
                embedding=embedding_to_blob(np.array([1, 0, 0], dtype=np.float32)),
                source=EmbeddingSources.BOOTSTRAP,
                captured_at=_naive(2015, 1, 1),
            )
        )
        session.commit()

        classifier = IdentityClassifier(session)
        probe = np.array([1, 0, 0], dtype=np.float32)

        result = classifier.classify(probe, captured_at=_naive(2026, 6, 1))

        assert result.identity == "Fibs"
        assert result.similarity > 0.99
        # The match itself is heavily temporally decayed...
        assert result.candidates[0].temporal_weight < 0.2
        # ...but that never touches the reported confidence.
        assert result.candidates[0].similarity > 0.99


def test_classifier_temporal_weight_fails_open_without_crop_date(engine):
    with Session(engine) as session:
        fibs = Identity(name="Fibs")

        session.add(fibs)
        session.flush()

        session.add(
            EmbeddingExample(
                identity_id=fibs.id,
                crop_path="fibs.jpg",
                embedding=embedding_to_blob(np.array([1, 0, 0], dtype=np.float32)),
                source=EmbeddingSources.BOOTSTRAP,
                captured_at=_naive(2015, 1, 1),
            )
        )
        session.commit()

        classifier = IdentityClassifier(session)
        probe = np.array([1, 0, 0], dtype=np.float32)

        # No captured_at at all -- "no date signal available" must never
        # be treated as suspicious, no matter how old the example is.
        result = classifier.classify(probe)

        assert result.candidates[0].temporal_weight == 1.0


def test_classifier_temporal_weight_fails_open_without_example_date(engine):
    with Session(engine) as session:
        fibs = Identity(name="Fibs")

        session.add(fibs)
        session.flush()

        session.add(
            EmbeddingExample(
                identity_id=fibs.id,
                crop_path="fibs.jpg",
                embedding=embedding_to_blob(np.array([1, 0, 0], dtype=np.float32)),
                source=EmbeddingSources.BOOTSTRAP,
                # captured_at left unset.
            )
        )
        session.commit()

        classifier = IdentityClassifier(session)
        probe = np.array([1, 0, 0], dtype=np.float32)

        result = classifier.classify(probe, captured_at=_naive(2026, 6, 1))

        assert result.candidates[0].temporal_weight == 1.0


def test_classification_service_handles_no_pending_crops(engine):
    from unittest.mock import Mock

    with Session(engine) as session:
        embedder = Mock()
        classifier = Mock()

        service = ClassificationService(
            session,
            embedder,
            classifier,
        )

        summary = service.classify()

        assert summary.classified == 0
        assert summary.identities == {}

        embedder.embed_batch.assert_not_called()
        classifier.classify.assert_not_called()


def test_classification_service_handles_no_reclassification_candidates(engine):
    from unittest.mock import Mock

    with Session(engine) as session:
        embedder = Mock()
        classifier = Mock()

        service = ClassificationService(
            session,
            embedder,
            classifier,
        )

        summary = service.classify(
            mode=ClassificationMode.LOW_CONFIDENCE,
        )

        assert summary.classified == 0
        assert summary.identities == {}

        embedder.embed_batch.assert_not_called()
        classifier.classify.assert_not_called()


def test_classifier_returns_one_candidate_per_identity(engine):
    with Session(engine) as session:
        hermann = Identity(name="Hermann")

        session.add(hermann)
        session.flush()

        session.add_all(
            [
                EmbeddingExample(
                    identity_id=hermann.id,
                    crop_path="hermann1.jpg",
                    embedding=embedding_to_blob(np.array([1, 0, 0], dtype=np.float32)),
                    source=EmbeddingSources.BOOTSTRAP,
                ),
                EmbeddingExample(
                    identity_id=hermann.id,
                    crop_path="hermann2.jpg",
                    embedding=embedding_to_blob(
                        np.array([0.99, 0.01, 0], dtype=np.float32)
                    ),
                    source=EmbeddingSources.BOOTSTRAP,
                ),
            ]
        )

        session.commit()

        classifier = IdentityClassifier(session)

        result = classifier.classify(np.array([1, 0, 0], dtype=np.float32))

        assert len(result.candidates) == 1
        assert result.candidates[0].identity == "Hermann"
