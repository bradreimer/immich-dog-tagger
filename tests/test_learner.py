from pathlib import Path

import numpy as np
from sqlalchemy.orm import Session

from immich_dog_tagger.database import create_database
from immich_dog_tagger.services.learner import Learner
from immich_dog_tagger.models import (
    EmbeddingExample,
)


class FakeEmbedder:
    def embed(
        self,
        image_path: Path,
    ):
        return np.array(
            [
                0.1,
                0.2,
                0.3,
            ],
            dtype=np.float32,
        )


def test_learner_creates_identity_and_embedding(
    tmp_path: Path,
):

    image_dir = tmp_path / "images"
    image_dir.mkdir()

    image = image_dir / "dog.jpg"
    image.write_bytes(
        b"fake",
    )

    engine = create_database(
        tmp_path,
    )

    with Session(engine) as session:
        learner = Learner(
            FakeEmbedder(),
            session,
        )

        count = learner.learn(
            "Hermann",
            image_dir,
        )

        assert count == 1

        result = session.query(EmbeddingExample).one()

        assert result.crop_path == str(image)
        assert result.source == "manual"


def test_learner_skips_existing_examples(engine, tmp_path):
    image_dir = tmp_path / "Fibs"
    image_dir.mkdir()

    image = image_dir / "fibs.jpg"
    image.write_bytes(b"test")

    embedder = FakeEmbedder()

    with Session(engine) as session:
        learner = Learner(
            embedder,
            session,
        )

        first = learner.learn(
            "Fibs",
            image_dir,
        )

        second = learner.learn(
            "Fibs",
            image_dir,
        )

    assert first == 1
    assert second == 0


def test_learner_records_source(engine, tmp_path):
    image_dir = tmp_path / "images"
    image_dir.mkdir()

    image = image_dir / "dog.jpg"
    image.write_bytes(b"fake")

    with Session(engine) as session:
        learner = Learner(
            FakeEmbedder(),
            session,
        )

        learner.learn(
            "Fibs",
            image_dir,
            source="review-confirmed",
        )

        result = session.query(EmbeddingExample).one()

        assert result.source == "review-confirmed"
