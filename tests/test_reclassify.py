import numpy as np
import pytest
from sqlalchemy.orm import Session

from immich_dog_tagger.embeddings import embedding_to_blob
from immich_dog_tagger.enums import (
    ClassificationPassStatus,
    ClassificationSources,
    Species,
)
from immich_dog_tagger.models import (
    ClassificationPass,
    Crop,
    CropClassification,
    EmbeddingExample,
    EmbeddingSources,
    Identity,
)
from immich_dog_tagger.services.reclassify import ReclassifyService


class FakeBatchEmbedder:
    """Returns a fixed embedding per call, tracking which paths it was asked to embed."""

    def __init__(self, vector=None):
        self.vector = vector if vector is not None else [1, 0, 0]
        self.calls: list[list] = []

    def embed_batch(self, paths):
        self.calls.append(list(paths))
        return np.array(
            [self.vector for _ in paths],
            dtype=np.float32,
        )


def _add_identity(session, name, vector, species=Species.DOG):
    identity = Identity(name=name, species=species)
    session.add(identity)
    session.flush()

    session.add(
        EmbeddingExample(
            identity_id=identity.id,
            crop_path=f"{species.value}-{name.lower()}.jpg",
            embedding=embedding_to_blob(np.array(vector, dtype=np.float32)),
            source=EmbeddingSources.BOOTSTRAP,
        )
    )
    return identity


def _add_auto_classification(
    session,
    path,
    *,
    identity=None,
    confidence=0.10,
    embedding=None,
    source=ClassificationSources.AUTO,
    species=Species.DOG,
):
    crop = Crop(detection_id=1, path=path, species=species)
    session.add(crop)
    session.flush()

    classification = CropClassification(
        crop=crop,
        identity=identity,
        confidence=confidence,
        source=source,
        embedding=embedding_to_blob(np.array(embedding, dtype=np.float32))
        if embedding is not None
        else None,
    )
    session.add(classification)
    session.commit()
    session.refresh(classification)
    return classification


def test_reclassify_with_no_labeled_examples_terminates_cleanly(engine):
    with Session(engine) as session:
        classification = _add_auto_classification(session, "one.jpg", identity=None)

        embedder = FakeBatchEmbedder()
        service = ReclassifyService(session, embedder)

        result = service.reclassify()

        assert result.status is ClassificationPassStatus.COMPLETED
        assert result.eligible_count == 1
        assert result.confident_count == 0
        assert result.changed_count == 0
        assert "No labeled examples" in result.message

        # Trend fields are still snapshotted on the zero-example short circuit.
        assert result.labeled_example_count == 0
        assert result.review_queue_size == 1

        session.refresh(classification)
        assert classification.identity is None
        assert embedder.calls == []


def test_reclassify_updates_auto_classification(engine):
    with Session(engine) as session:
        _add_identity(session, "Hermann", [1, 0, 0])

        classification = _add_auto_classification(
            session,
            "hermann_photo.jpg",
            identity=None,
            confidence=-1.0,
            embedding=[1, 0, 0],
        )

        embedder = FakeBatchEmbedder()
        service = ReclassifyService(session, embedder)

        result = service.reclassify()

        assert result.status is ClassificationPassStatus.COMPLETED
        assert result.eligible_count == 1
        assert result.confident_count == 1
        assert result.changed_count == 1

        # One bootstrap example exists; the crop is now confident, so it's
        # no longer in the review queue.
        assert result.labeled_example_count == 1
        assert result.review_queue_size == 0

        session.refresh(classification)
        assert classification.identity == "Hermann"
        assert classification.classifier_version == "v1"
        assert classification.classification_pass_id == result.pass_id

        # Embedding was already cached on the row, so it must not be recomputed.
        assert embedder.calls == []


def test_reclassify_mixed_species_batch_is_species_scoped_and_idempotent(engine):
    # DT-1110: a single ReclassifyService run shares one IdentityClassifier
    # instance across every eligible crop regardless of species. A dog
    # "Max" and a cat "Max" with the *same* embedding vector are the
    # sharpest test of that -- without per-species scoping in the shared
    # classifier's example cache, the cat crop could resolve to the dog
    # identity (or vice versa) since the name and embedding alone can't
    # distinguish them.
    with Session(engine) as session:
        _add_identity(session, "Max", [1, 0, 0], species=Species.DOG)
        _add_identity(session, "Max", [1, 0, 0], species=Species.CAT)

        dog_classification = _add_auto_classification(
            session,
            "dog_photo.jpg",
            identity=None,
            confidence=-1.0,
            embedding=[1, 0, 0],
            species=Species.DOG,
        )
        cat_classification = _add_auto_classification(
            session,
            "cat_photo.jpg",
            identity=None,
            confidence=-1.0,
            embedding=[1, 0, 0],
            species=Species.CAT,
        )

        embedder = FakeBatchEmbedder()
        service = ReclassifyService(session, embedder)

        result = service.reclassify()

        assert result.status is ClassificationPassStatus.COMPLETED
        assert result.eligible_count == 2
        assert result.confident_count == 2
        assert result.changed_count == 2

        session.refresh(dog_classification)
        session.refresh(cat_classification)

        assert dog_classification.identity == "Max"
        assert cat_classification.identity == "Max"
        assert (
            dog_classification.matched_example_id
            != cat_classification.matched_example_id
        )

        # Re-running with no new reviews changes nothing for either crop --
        # idempotency must hold per-species, not just in aggregate.
        second = service.reclassify()

        assert second.changed_count == 0

        session.refresh(dog_classification)
        session.refresh(cat_classification)

        assert dog_classification.identity == "Max"
        assert cat_classification.identity == "Max"


def test_reclassify_reuses_cached_embedding_and_computes_missing_ones(engine):
    with Session(engine) as session:
        _add_identity(session, "Hermann", [1, 0, 0])

        cached = _add_auto_classification(
            session,
            "cached.jpg",
            embedding=[1, 0, 0],
        )
        legacy = _add_auto_classification(
            session,
            "legacy.jpg",
            embedding=None,
        )

        embedder = FakeBatchEmbedder(vector=[1, 0, 0])
        service = ReclassifyService(session, embedder)

        service.reclassify()

        # Only the row without a cached embedding should have triggered an embed call.
        from pathlib import Path

        assert embedder.calls == [[Path("legacy.jpg")]]

        session.refresh(cached)
        session.refresh(legacy)
        assert cached.identity == "Hermann"
        assert legacy.identity == "Hermann"
        assert legacy.embedding is not None


def test_reclassify_snapshots_review_queue_reflecting_post_pass_state(engine):
    with Session(engine) as session:
        _add_identity(session, "Hermann", [1, 0, 0])

        # Becomes confident after reclassify -- leaves the queue.
        _add_auto_classification(session, "hermann.jpg", embedding=[1, 0, 0])

        # No matching example -- stays Unknown, stays in the queue.
        _add_auto_classification(session, "stranger.jpg", embedding=[0, 1, 0])

        embedder = FakeBatchEmbedder(vector=[1, 0, 0])
        service = ReclassifyService(session, embedder)

        result = service.reclassify()

        assert result.labeled_example_count == 1
        assert result.review_queue_size == 1


def test_reclassify_never_touches_reviewed_ground_truth(engine):
    with Session(engine) as session:
        _add_identity(session, "Hermann", [1, 0, 0])

        reviewed = _add_auto_classification(
            session,
            "reviewed.jpg",
            identity="Fibs",
            confidence=1.0,
            embedding=[1, 0, 0],
            source=ClassificationSources.REVIEW,
        )

        embedder = FakeBatchEmbedder()
        service = ReclassifyService(session, embedder)

        result = service.reclassify()

        # Reviewed row is not eligible at all.
        assert result.eligible_count == 0

        session.refresh(reviewed)
        assert reviewed.identity == "Fibs"
        assert reviewed.confidence == 1.0
        assert reviewed.classification_pass_id is None


def test_reclassify_is_idempotent_when_rerun_with_unchanged_inputs(engine):
    with Session(engine) as session:
        _add_identity(session, "Hermann", [1, 0, 0])

        _add_auto_classification(
            session,
            "hermann_photo.jpg",
            embedding=[1, 0, 0],
        )

        embedder = FakeBatchEmbedder()
        service = ReclassifyService(session, embedder)

        first = service.reclassify()
        second = service.reclassify()

        assert first.changed_count == 1
        assert second.changed_count == 0
        assert second.confident_count == 1
        assert second.pass_id != first.pass_id


def test_reclassify_processes_in_batches_committing_progress(engine):
    with Session(engine) as session:
        _add_identity(session, "Hermann", [1, 0, 0])

        for i in range(5):
            _add_auto_classification(
                session,
                f"photo-{i}.jpg",
                embedding=[1, 0, 0],
            )

        embedder = FakeBatchEmbedder()
        service = ReclassifyService(session, embedder, batch_size=2)

        result = service.reclassify()

        assert result.eligible_count == 5
        assert result.confident_count == 5

        passes = session.query(ClassificationPass).all()
        assert len(passes) == 1
        assert passes[0].status is ClassificationPassStatus.COMPLETED


def test_reclassify_failure_marks_pass_failed_and_preserves_earlier_batches(engine):
    with Session(engine) as session:
        _add_identity(session, "Hermann", [1, 0, 0])

        for i in range(3):
            _add_auto_classification(
                session,
                f"photo-{i}.jpg",
                embedding=[1, 0, 0],
            )

        embedder = FakeBatchEmbedder()
        service = ReclassifyService(session, embedder, batch_size=1)

        call_count = {"n": 0}
        original_commit = session.commit

        def flaky_commit():
            call_count["n"] += 1
            # Commit order: (1) pass creation, (2) eligible_count, (3) first
            # batch. Let those succeed, then blow up on the second batch.
            if call_count["n"] == 4:
                raise RuntimeError("simulated database error")
            original_commit()

        session.commit = flaky_commit

        with pytest.raises(RuntimeError, match="simulated database error"):
            service.reclassify()

        session.commit = original_commit
        session.rollback()

        classification_pass = session.query(ClassificationPass).one()
        assert classification_pass.status is ClassificationPassStatus.FAILED
        assert classification_pass.error_message == "simulated database error"

        # A partial pass has no well-defined final snapshot.
        assert classification_pass.labeled_example_count is None
        assert classification_pass.review_queue_size is None

        # The first batch's update was already committed before the failure.
        updated = (
            session.query(CropClassification)
            .filter(CropClassification.classification_pass_id == classification_pass.id)
            .count()
        )
        assert updated == 1
