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


def test_learner_commits_before_each_embed_call(engine, tmp_path):
    """
    Regression test for issue #239: embedding image N must never run while
    a previous write (identity creation, or image N-1's EmbeddingExample) is
    still uncommitted -- otherwise SQLite's write lock is held for however
    long embedding takes, instead of just for the write itself, and a
    concurrent writer (e.g. POST /jobs) fails with "database is locked".

    Verified with a second, independent connection that tries to acquire
    SQLite's write lock (`BEGIN IMMEDIATE`) at the moment each image is
    embedded -- `session.new`/`session.dirty` can't be used for this, since
    autoflush clears them the moment a write is *flushed*, even though the
    underlying SQLite transaction (and its write lock) isn't released until
    `commit()`.
    """
    import sqlite3

    image_dir = tmp_path / "images"
    image_dir.mkdir()

    for name in ("a.jpg", "b.jpg", "c.jpg"):
        (image_dir / name).write_bytes(b"fake")

    db_path = tmp_path / "state.db"
    probe = sqlite3.connect(str(db_path), timeout=0.05)

    try:
        with Session(engine) as session:

            class RecordingEmbedder:
                def __init__(self):
                    self.lock_held_on_embed: list[bool] = []

                def embed(self, image_path: Path):
                    try:
                        probe.execute("BEGIN IMMEDIATE")
                        probe.execute("ROLLBACK")
                        held = False
                    except sqlite3.OperationalError:
                        held = True
                    self.lock_held_on_embed.append(held)
                    return np.array([0.1, 0.2, 0.3], dtype=np.float32)

            embedder = RecordingEmbedder()
            learner = Learner(embedder, session)

            result = learner.learn("Hermann", image_dir)

            assert result.imported == 3
            assert embedder.lock_held_on_embed == [False, False, False]
    finally:
        probe.close()


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


def test_learn_image_supersedes_stale_example_under_previous_identity(engine, tmp_path):
    """Re-reviewing a crop under a different identity must not leave a stale
    example for the old identity behind (DT-1003 leakage regression)."""
    image = tmp_path / "dog.jpg"
    image.write_bytes(b"fake")

    with Session(engine) as session:
        learner = Learner(FakeEmbedder(), session)

        learner.learn_image("Fibs", image, source=EmbeddingSources.REVIEW)
        session.commit()

        learner.learn_image("Hermann", image, source=EmbeddingSources.REVIEW)
        session.commit()

        examples = session.query(EmbeddingExample).all()

        assert len(examples) == 1
        assert examples[0].identity.name == "Hermann"
        assert examples[0].crop_path == str(image)


def test_forget_image_removes_examples_for_any_identity(engine, tmp_path):
    image = tmp_path / "dog.jpg"
    image.write_bytes(b"fake")

    with Session(engine) as session:
        learner = Learner(FakeEmbedder(), session)

        learner.learn_image("Fibs", image, source=EmbeddingSources.REVIEW)
        session.commit()

        removed = learner.forget_image(image)
        session.commit()

        assert removed == 1
        assert session.query(EmbeddingExample).count() == 0


def test_forget_image_is_a_noop_when_nothing_matches(engine, tmp_path):
    image = tmp_path / "dog.jpg"

    with Session(engine) as session:
        learner = Learner(FakeEmbedder(), session)

        removed = learner.forget_image(image)

        assert removed == 0
