from pathlib import Path
import numpy as np
from sqlalchemy.orm import Session

from immich_dog_tagger.database import create_database
from immich_dog_tagger.models import EmbeddingExample, EmbeddingSources
from immich_dog_tagger.services.learner import Learner


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

        assert count.imported == 1
        assert count.skipped_existing == 0

        result = session.query(EmbeddingExample).one()

        assert result.crop_path == str(image)
        assert result.source == EmbeddingSources.BOOTSTRAP


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

    assert first.imported == 1
    assert first.skipped_existing == 0

    assert second.imported == 0
    assert second.skipped_existing == 1


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
            source=EmbeddingSources.REVIEW,
        )

        result = session.query(EmbeddingExample).one()

        assert result.source == EmbeddingSources.REVIEW


def test_learner_skips_non_images(engine, tmp_path):
    image_dir = tmp_path / "images"
    image_dir.mkdir()

    (image_dir / "dog.jpg").write_bytes(b"fake")
    (image_dir / "notes.txt").write_text("ignore")

    with Session(engine) as session:
        learner = Learner(
            FakeEmbedder(),
            session,
        )

        count = learner.learn(
            "Fibs",
            image_dir,
        )

    assert count.imported == 1
    assert count.skipped_existing == 0


def test_learn_image_creates_embedding_example(engine, tmp_path):
    from unittest.mock import Mock
    import numpy as np

    from sqlalchemy.orm import Session

    from immich_dog_tagger.models import (
        EmbeddingExample,
        EmbeddingSources,
    )

    image = tmp_path / "hermann.jpg"
    image.write_bytes(b"fake")

    embedder = Mock()
    embedder.embed.return_value = np.array(
        [1, 0, 0],
        dtype=np.float32,
    )

    with Session(engine) as session:
        learner = Learner(
            embedder,
            session,
        )

        result = learner.learn_image(
            "Hermann",
            image,
            source=EmbeddingSources.REVIEW,
        )

        assert result is True

        example = session.query(EmbeddingExample).one()

        assert example.crop_path == str(image)
        assert example.source == EmbeddingSources.REVIEW
