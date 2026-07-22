import numpy as np
from sqlalchemy.orm import Session

from immich_dog_tagger.classifier import IdentityClassifier
from immich_dog_tagger.embeddings import embedding_to_blob
from immich_dog_tagger.models import (
    Identity,
    EmbeddingExample,
    EmbeddingSources,
)


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
        assert result.confidence > 0.9
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
