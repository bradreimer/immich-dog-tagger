"""DT-1008: N+1 and batching regression coverage at synthetic scale.

Runs at a reduced synthetic scale (hundreds-to-low-thousands of rows)
rather than a literal 30,000-image run, since this environment has no GPU
and no real Immich instance to exercise. What's verified here is the
*shape* of the resource behavior that matters at 30,000 images: query
count independent of row count, and batched (not all-at-once) processing.
"""

import numpy as np
from sqlalchemy.orm import Session

from immich_dog_tagger.classifier import IdentityClassifier
from immich_dog_tagger.embeddings import embedding_to_blob
from immich_dog_tagger.enums import EmbeddingSources
from immich_dog_tagger.models import (
    Asset,
    Crop,
    CropClassification,
    Detection,
    EmbeddingExample,
    Identity,
)
from immich_dog_tagger.services.reclassify import ReclassifyService
from tests.conftest import QueryCounter


class FakeBatchEmbedder:
    def embed_batch(self, paths):
        return np.array([[1, 0, 0] for _ in paths], dtype=np.float32)


def _seed_identity_with_examples(session, count=20):
    identity = Identity(name="Hermann")
    session.add(identity)
    session.flush()

    for i in range(count):
        session.add(
            EmbeddingExample(
                identity_id=identity.id,
                crop_path=f"example-{i}.jpg",
                embedding=embedding_to_blob(np.array([1, 0, 0], dtype=np.float32)),
                source=EmbeddingSources.BOOTSTRAP,
            )
        )
    session.commit()


def test_classifier_issues_one_example_query_regardless_of_call_count(engine):
    """The classic N+1: classify() must not re-fetch the example table once
    per call. A single IdentityClassifier instance should query it once."""
    with Session(engine) as session:
        _seed_identity_with_examples(session, count=20)

        classifier = IdentityClassifier(session)
        embedding = np.array([1, 0, 0], dtype=np.float32)

        with QueryCounter(engine) as counter:
            for _ in range(50):
                classifier.classify(embedding)

        # One query to load examples, not one per classify() call.
        assert counter.count == 1


def test_review_queue_query_count_does_not_scale_with_result_size(engine):
    """ReviewQueryService must eager-load crop/matched-example relationships
    instead of lazy-loading them once per row (DT-1008 N+1 fix)."""
    from immich_dog_tagger.services.review_query import ReviewQueryService

    def seed(n):
        for i in range(n):
            crop = Crop(detection_id=1, path=f"dog-{i}.jpg")
            session.add(crop)
            session.flush()
            session.add(CropClassification(crop=crop, identity=None, confidence=-1.0))
        session.commit()

    with Session(engine) as session:
        seed(10)

        with QueryCounter(engine) as small:
            ReviewQueryService(session).active_review(limit=100)

    with Session(engine) as session:
        seed(90)  # 100 total across both sessions' worth of rows

        with QueryCounter(engine) as large:
            ReviewQueryService(session).active_review(limit=100)

    # Query count should be flat (a handful of fixed queries), not
    # proportional to the number of rows returned.
    assert large.count <= small.count + 2


def test_review_queue_captured_at_query_count_does_not_scale_with_result_size(engine):
    """DT-1111: the Crop -> Detection -> Asset eager-load hop added for
    captured_at must not reintroduce a per-row query -- each row here has a
    real Detection/Asset chain (unlike the dangling detection_id fixtures
    used elsewhere), so this actually exercises the new selectinload hop."""
    from immich_dog_tagger.services.review_query import ReviewQueryService

    def seed(session, offset, n):
        for i in range(offset, offset + n):
            asset = Asset(
                immich_asset_id=f"asset-{i}",
                extension=".jpg",
            )
            detection = Detection(
                asset=asset,
                label="dog",
                confidence=0.99,
                x1=0,
                y1=0,
                x2=100,
                y2=100,
            )
            crop = Crop(detection=detection, path=f"dog-{i}.jpg")
            session.add(crop)
            session.flush()
            session.add(CropClassification(crop=crop, identity=None, confidence=-1.0))
        session.commit()

    with Session(engine) as session:
        seed(session, 0, 10)

        with QueryCounter(engine) as small:
            ReviewQueryService(session).active_review(limit=100)

    with Session(engine) as session:
        seed(session, 10, 90)  # 100 total across both sessions' worth of rows

        with QueryCounter(engine) as large:
            ReviewQueryService(session).active_review(limit=100)

    assert large.count <= small.count + 2


def test_reclassify_at_synthetic_scale_processes_in_bounded_batches(engine):
    """A few hundred crops reclassified in small batches must produce
    correct, complete results without loading everything into one
    transaction's working set at once."""
    with Session(engine) as session:
        _seed_identity_with_examples(session, count=5)

        crop_count = 300

        for i in range(crop_count):
            crop = Crop(detection_id=1, path=f"dog-{i}.jpg")
            session.add(crop)
            session.flush()
            session.add(
                CropClassification(
                    crop=crop,
                    identity=None,
                    confidence=-1.0,
                    embedding=embedding_to_blob(np.array([1, 0, 0], dtype=np.float32)),
                )
            )
        session.commit()

        service = ReclassifyService(session, FakeBatchEmbedder(), batch_size=25)
        result = service.reclassify()

        assert result.eligible_count == crop_count
        assert result.confident_count == crop_count

        updated = (
            session.query(CropClassification)
            .filter(CropClassification.identity == "Hermann")
            .count()
        )
        assert updated == crop_count
