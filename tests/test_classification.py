import numpy as np
import pytest
from sqlalchemy.orm import Session

from immich_dog_tagger.classifier import ClassificationResult
from immich_dog_tagger.enums import ClassificationMode
from immich_dog_tagger.models import (
    Asset,
    ClassificationSources,
    Crop,
    CropClassification,
    Detection,
)
from immich_dog_tagger.services.classification import BATCH_SIZE, ClassificationService


class FakeBatchEmbedder:
    def embed_batch(self, paths):
        return np.array(
            [
                [1, 0, 0],
                [0, 1, 0],
            ],
            dtype=np.float32,
        )


def test_classification_service_creates_classification(engine):
    from unittest.mock import Mock

    with Session(engine) as session:
        asset = Asset(
            immich_asset_id="asset1",
            checksum="checksum",
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

        crop = Crop(
            detection=detection,
            path="test.jpg",
        )

        session.add(crop)
        session.commit()

        embedder = Mock()
        embedder.embed_batch.return_value = np.zeros(
            (1, 512),
            dtype=np.float32,
        )

        classifier = Mock()
        classifier.classify.return_value = ClassificationResult(
            identity="Hermann",
            similarity=0.95,
            matched_example_id=42,
            candidates=[],
        )

        service = ClassificationService(
            session,
            embedder,
            classifier,
        )

        summary = service.classify()

        assert summary.classified == 1
        assert summary.identities["Hermann"] == 1

        result = session.query(CropClassification).one()

        assert result.identity == "Hermann"
        assert result.confidence == 0.95
        assert result.crop.id == crop.id
        assert result.matched_example_id == 42
        assert result.source == ClassificationSources.AUTO


def test_classification_service_skips_existing_classification_by_default(engine):
    from unittest.mock import Mock

    with Session(engine) as session:
        crop = Crop(
            detection_id=1,
            path="test.jpg",
        )

        session.add(crop)
        session.flush()

        existing = CropClassification(
            crop=crop,
            identity="Fibs",
            confidence=0.95,
            source=ClassificationSources.MANUAL,
        )

        session.add(existing)
        session.commit()

        embedder = Mock()
        classifier = Mock()

        service = ClassificationService(
            session,
            embedder,
            classifier,
        )

        summary = service.classify()

        assert summary.classified == 0

        embedder.embed_batch.assert_not_called()
        classifier.classify.assert_not_called()

        result = session.query(CropClassification).one()

        assert result.identity == "Fibs"
        assert result.source == ClassificationSources.MANUAL


def test_classification_service_force_updates_existing_classification(engine):
    from unittest.mock import Mock

    with Session(engine) as session:
        crop = Crop(
            detection_id=1,
            path="test.jpg",
        )

        session.add(crop)
        session.flush()

        existing = CropClassification(
            crop=crop,
            identity="Fibs",
            confidence=0.60,
            source=ClassificationSources.MANUAL,
        )

        session.add(existing)
        session.commit()

        embedder = Mock()
        embedder.embed_batch.return_value = np.array(
            [[1, 0, 0]],
            dtype=np.float32,
        )

        classifier = Mock()
        classifier.classify.return_value = ClassificationResult(
            identity="Hermann",
            similarity=0.95,
            matched_example_id=42,
            candidates=[],
        )

        service = ClassificationService(
            session,
            embedder,
            classifier,
        )

        summary = service.classify(
            mode=ClassificationMode.ALL,
        )

        assert summary.classified == 1

        result = session.query(CropClassification).one()

        assert result.identity == "Hermann"
        assert result.confidence == 0.95
        assert result.matched_example_id == 42
        assert result.source == ClassificationSources.MANUAL

        # Important: force should still update in-place
        assert session.query(CropClassification).count() == 1


def test_classification_service_respects_limit(engine):
    from unittest.mock import Mock

    with Session(engine) as session:
        session.add_all(
            [
                Crop(
                    detection_id=1,
                    path="one.jpg",
                ),
                Crop(
                    detection_id=2,
                    path="two.jpg",
                ),
                Crop(
                    detection_id=3,
                    path="three.jpg",
                ),
            ]
        )

        session.commit()

        embedder = Mock()
        embedder.embed_batch.return_value = np.array(
            [
                [1, 0, 0],
            ],
            dtype=np.float32,
        )

        classifier = Mock()
        classifier.classify.return_value = ClassificationResult(
            identity="Fibs",
            similarity=0.95,
            matched_example_id=None,
            candidates=[],
        )

        service = ClassificationService(
            session,
            embedder,
            classifier,
        )

        summary = service.classify(
            limit=1,
        )

        assert summary.classified == 1


def test_classification_service_handles_unknown_identity(engine):
    from unittest.mock import Mock

    with Session(engine) as session:
        asset = Asset(
            immich_asset_id="asset1",
            checksum="checksum",
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

        crop = Crop(
            detection=detection,
            path="test.jpg",
        )

        session.add(crop)
        session.commit()

        embedder = Mock()
        embedder.embed_batch.return_value = np.zeros(
            (1, 512),
            dtype=np.float32,
        )

        classifier = Mock()
        classifier.classify.return_value = ClassificationResult(
            identity=None,
            similarity=0.12,
            matched_example_id=None,
            candidates=[],
        )

        service = ClassificationService(
            session,
            embedder,
            classifier,
        )

        summary = service.classify()

        assert summary.classified == 1
        assert summary.identities["Unknown"] == 1

        result = session.query(CropClassification).one()

        assert result.identity is None
        assert result.confidence == 0.12
        assert result.crop.id == crop.id
        assert result.matched_example_id is None
        assert result.source == ClassificationSources.AUTO


def test_classification_service_uses_batch_embedding(engine):
    from unittest.mock import Mock

    with Session(engine) as session:
        crop1 = Crop(
            detection_id=1,
            path="one.jpg",
        )

        crop2 = Crop(
            detection_id=2,
            path="two.jpg",
        )

        session.add_all(
            [
                crop1,
                crop2,
            ]
        )
        session.commit()

        embedder = Mock()

        embedder.embed_batch.return_value = np.array(
            [
                [1, 0, 0],
                [0, 1, 0],
            ],
            dtype=np.float32,
        )

        classifier = Mock()
        classifier.classify.return_value = ClassificationResult(
            identity="Fibs",
            similarity=0.95,
            matched_example_id=None,
            candidates=[],
        )

        service = ClassificationService(
            session,
            embedder,
            classifier,
        )

        summary = service.classify()

        assert summary.classified == 2

        embedder.embed_batch.assert_called_once_with(
            [
                "one.jpg",
                "two.jpg",
            ]
        )


def test_classification_service_reclassifies_existing_classification(engine):
    from unittest.mock import Mock

    with Session(engine) as session:
        crop = Crop(
            detection_id=1,
            path="test.jpg",
        )

        session.add(crop)
        session.flush()

        existing = CropClassification(
            crop=crop,
            identity=None,
            confidence=0.2,
        )

        session.add(existing)
        session.commit()

        embedder = Mock()
        embedder.embed_batch.return_value = np.array(
            [[1, 0, 0]],
            dtype=np.float32,
        )

        classifier = Mock()
        classifier.classify.return_value = ClassificationResult(
            identity="Hermann",
            similarity=0.95,
            matched_example_id=42,
            candidates=[],
        )

        service = ClassificationService(
            session,
            embedder,
            classifier,
        )

        service.classify(threshold=0.80, mode=ClassificationMode.LOW_CONFIDENCE)

        result = session.query(CropClassification).one()

        assert result.identity == "Hermann"
        assert result.confidence == 0.95
        assert result.matched_example_id == 42
        assert result.source == ClassificationSources.AUTO


def test_classification_service_passes_threshold(engine):
    from unittest.mock import Mock

    with Session(engine) as session:
        crop = Crop(
            detection_id=1,
            path="test.jpg",
        )

        session.add(crop)
        session.commit()

        embedder = Mock()
        embedder.embed_batch.return_value = np.zeros(
            (1, 512),
            dtype=np.float32,
        )

        classifier = Mock()
        classifier.classify.return_value = ClassificationResult(
            identity=None,
            similarity=0.5,
            matched_example_id=None,
            candidates=[],
        )

        service = ClassificationService(
            session,
            embedder,
            classifier,
        )

        service.classify(
            threshold=0.65,
        )

        classifier.classify.assert_called_once()

        assert classifier.classify.call_args.kwargs["threshold"] == 0.65


def test_classify_all_includes_classified_crops(engine):
    from unittest.mock import Mock

    with Session(engine) as session:
        crop = Crop(
            detection_id=1,
            path="dog.jpg",
        )

        session.add(crop)
        session.flush()

        session.add(
            CropClassification(
                crop=crop,
                identity="Fibs",
                confidence=0.50,
                source=ClassificationSources.MANUAL,
            )
        )

        session.commit()

        embedder = Mock()
        embedder.embed_batch.return_value = np.array(
            [
                [1, 0, 0],
            ],
            dtype=np.float32,
        )

        classifier = Mock()
        classifier.classify.return_value = ClassificationResult(
            identity="Hermann",
            similarity=0.95,
            matched_example_id=42,
            candidates=[],
        )

        service = ClassificationService(
            session,
            embedder,
            classifier,
        )

        summary = service.classify(
            mode=ClassificationMode.ALL,
        )

    assert summary.classified == 1


def test_classification_service_commits_in_batches_of_500(engine):
    from unittest.mock import Mock

    # Regression test for issue #104: a single commit at the end of the
    # whole batch held state.db's write lock for the run's entire duration,
    # blocking every other reader for as long as classification took.
    total = BATCH_SIZE + 200

    with Session(engine) as session:
        crops = [
            Crop(
                detection_id=index,
                path=f"{index}.jpg",
            )
            for index in range(total)
        ]
        session.add_all(crops)
        session.commit()

        embedder = Mock()
        embedder.embed_batch.return_value = np.zeros(
            (total, 3),
            dtype=np.float32,
        )

        classifier = Mock()
        classifier.classify.return_value = ClassificationResult(
            identity=None,
            similarity=0.0,
            matched_example_id=None,
            candidates=[],
        )

        service = ClassificationService(
            session,
            embedder,
            classifier,
        )

        commit_calls = []
        original_commit = session.commit

        def counting_commit():
            commit_calls.append(1)
            original_commit()

        session.commit = counting_commit

        summary = service.classify(
            mode=ClassificationMode.ALL,
        )

        assert summary.classified == total
        # One commit at the BATCH_SIZE boundary, one final commit for the
        # remaining 200 -- proves the loop doesn't hold everything for a
        # single commit at the end.
        assert len(commit_calls) == 2
        assert session.query(CropClassification).count() == total


def test_classification_service_failure_leaves_only_prior_batches_committed(
    engine,
):
    from unittest.mock import Mock

    # Regression test for issue #104: a failure partway through a run must
    # not discard batches already committed, the same guarantee issue #99
    # established for scan/download -- and the still-uncommitted straggler
    # batch must not survive either, since PipelineJobRunner commits the
    # job's own failure status on this same session right after.
    total = BATCH_SIZE + 200
    fail_at = BATCH_SIZE + 100

    with Session(engine) as session:
        crops = [
            Crop(
                detection_id=index,
                path=f"{index}.jpg",
            )
            for index in range(total)
        ]
        session.add_all(crops)
        session.commit()

        embedder = Mock()
        embedder.embed_batch.return_value = np.zeros(
            (total, 3),
            dtype=np.float32,
        )

        calls = {"count": 0}

        def flaky_classify(*args, **kwargs):
            calls["count"] += 1

            if calls["count"] == fail_at:
                raise ValueError("simulated failure")

            return ClassificationResult(
                identity=None,
                similarity=0.0,
                matched_example_id=None,
                candidates=[],
            )

        classifier = Mock()
        classifier.classify.side_effect = flaky_classify

        service = ClassificationService(
            session,
            embedder,
            classifier,
        )

        with pytest.raises(ValueError, match="simulated failure"):
            service.classify(
                mode=ClassificationMode.ALL,
            )

    with Session(engine) as verify_session:
        # Only the first full batch (500) was committed; the failure at
        # 600 happened inside the still-uncommitted second batch, which
        # was rolled back in full rather than left for a later commit
        # (e.g. the caller's job-failure commit) to persist by accident.
        assert verify_session.query(CropClassification).count() == BATCH_SIZE
