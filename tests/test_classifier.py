import numpy as np
from sqlalchemy.orm import Session

from immich_dog_tagger.classifier import IdentityClassifier
from immich_dog_tagger.embeddings import embedding_to_blob
from immich_dog_tagger.enums import ClassificationMode
from immich_dog_tagger.models import (
    EmbeddingExample,
    EmbeddingSources,
    Identity,
)
from immich_dog_tagger.services.classification import ClassificationService


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
