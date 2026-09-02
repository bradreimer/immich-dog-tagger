import numpy as np
from sqlalchemy.orm import Session

from immich_dog_tagger.classifier import ClassificationResult
from immich_dog_tagger.enums import AssetStatus, ClassificationMode
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


def test_classification_service_commits_in_batches(engine):
    from unittest.mock import Mock

    # Regression test for issue #104: a single commit at the end of the
    # whole batch held state.db's write lock for the run's entire duration,
    # blocking every other reader for as long as classification took.
    # BATCH_SIZE is also this service's select/embed/commit chunk size
    # (issue #111), so a chunk-and-a-half gives exactly one full chunk plus
    # one partial one -- two commits, regardless of BATCH_SIZE's value.
    total = BATCH_SIZE + BATCH_SIZE // 2

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
        # One commit for the first full chunk, one final commit for the
        # remainder -- proves the loop doesn't hold everything for a single
        # commit at the end.
        assert len(commit_calls) == 2
        assert session.query(CropClassification).count() == total


def test_classification_service_unexpected_failure_stops_run_without_raising(
    engine,
):
    from unittest.mock import Mock

    # Issue #194/FR-10/FR-11: an unexpected error partway through a chunk
    # (as opposed to a missing crop file, which is isolated per crop) must
    # not fail the whole job -- classify() discards that chunk's
    # uncommitted work and stops the run cleanly. Batches already committed
    # survive, and mode=ALL's query is stateless, so the next classify()
    # call simply retries what didn't get committed.
    total = BATCH_SIZE + 200
    fail_at = BATCH_SIZE + max(1, BATCH_SIZE // 2)

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

        summary = service.classify(
            mode=ClassificationMode.ALL,
        )

        # Only the first full chunk's worth is reflected -- the chunk the
        # failure happened in was discarded, and the run stopped there
        # rather than continuing past it.
        assert summary.classified == BATCH_SIZE

    with Session(engine) as verify_session:
        # Only the first full batch was committed; the failure happened
        # inside the still-uncommitted second batch, which was rolled back
        # in full rather than left for a later commit (e.g. the caller's
        # job-failure commit) to persist by accident.
        assert verify_session.query(CropClassification).count() == BATCH_SIZE


def test_classification_service_honors_should_cancel(engine):
    from unittest.mock import Mock

    # Issue #111: should_cancel is checked between chunks (each chunk is
    # select+embed+commit as one atomic unit here, see BATCH_SIZE's
    # docstring), so cancellation never loses a chunk that already
    # committed.
    total = 3 * BATCH_SIZE

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
        embedder.embed_batch.side_effect = lambda paths: np.zeros(
            (len(paths), 3), dtype=np.float32
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

        calls = {"count": 0}

        def should_cancel():
            calls["count"] += 1
            # Let the first two chunks through, stop before the third.
            return calls["count"] > 2

        summary = service.classify(
            mode=ClassificationMode.ALL,
            should_cancel=should_cancel,
        )

        assert summary.classified == 2 * BATCH_SIZE

    with Session(engine) as verify_session:
        assert verify_session.query(CropClassification).count() == 2 * BATCH_SIZE


def test_classification_service_chunks_without_an_explicit_limit(engine):
    """Issue #111: without this, an unlimited Classify job would embed
    every eligible crop in one uninterruptible call before should_cancel
    ever got checked -- classify() must select/embed/commit in its own
    internal chunks regardless of whether a limit was passed."""
    from unittest.mock import Mock

    total = BATCH_SIZE + max(1, BATCH_SIZE // 2)

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
        embed_call_sizes = []

        def fake_embed_batch(paths):
            embed_call_sizes.append(len(paths))
            return np.zeros((len(paths), 3), dtype=np.float32)

        embedder.embed_batch.side_effect = fake_embed_batch

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

        summary = service.classify(mode=ClassificationMode.ALL)

        assert summary.classified == total
        # Never one call embedding everything -- each call is bounded by
        # BATCH_SIZE.
        assert embed_call_sizes == [BATCH_SIZE, total - BATCH_SIZE]


def test_classification_isolates_missing_crop_file(engine, tmp_path):
    from unittest.mock import Mock

    good_path = tmp_path / "good.jpg"
    good_path.write_bytes(b"data")
    missing_path = tmp_path / "missing.jpg"

    with Session(engine) as session:
        good_asset = Asset(immich_asset_id="good", checksum="a", extension=".jpg")
        missing_asset = Asset(immich_asset_id="missing", checksum="b", extension=".jpg")
        session.add_all([good_asset, missing_asset])
        session.flush()

        good_detection = Detection(
            asset=good_asset, label="dog", confidence=0.9, x1=0, y1=0, x2=1, y2=1
        )
        missing_detection = Detection(
            asset=missing_asset, label="dog", confidence=0.9, x1=0, y1=0, x2=1, y2=1
        )
        session.add_all([good_detection, missing_detection])
        session.flush()

        good_crop = Crop(detection=good_detection, path=str(good_path))
        missing_crop = Crop(detection=missing_detection, path=str(missing_path))
        session.add_all([good_crop, missing_crop])
        session.commit()

        embedder = Mock()

        def fake_embed_batch(paths):
            if str(missing_path) in paths:
                raise FileNotFoundError(str(missing_path))

            return np.array([[1, 0, 0]], dtype=np.float32)

        embedder.embed_batch.side_effect = fake_embed_batch

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

        summary = service.classify(mode=ClassificationMode.ALL)

        assert summary.classified == 1
        assert summary.failed == 1

        session.refresh(missing_asset)

        assert missing_asset.status is AssetStatus.CLASSIFICATION_FAILED

        result = session.query(CropClassification).one()

        assert result.crop_id == good_crop.id


def test_classification_asset_id_scopes_to_one_asset(engine):
    from unittest.mock import Mock

    # Issue #226's Repair action classifies only the one photo it just
    # re-detected -- asset_id keeps a mode=PENDING classify from also
    # picking up unrelated pending crops elsewhere in the library.
    with Session(engine) as session:
        target_asset = Asset(
            immich_asset_id="target",
            checksum="xyz",
            extension=".jpg",
        )
        other_asset = Asset(
            immich_asset_id="other",
            checksum="abc",
            extension=".jpg",
        )

        target_detection = Detection(
            asset=target_asset,
            label="dog",
            confidence=0.99,
            x1=0,
            y1=0,
            x2=100,
            y2=100,
        )
        other_detection = Detection(
            asset=other_asset,
            label="dog",
            confidence=0.99,
            x1=0,
            y1=0,
            x2=100,
            y2=100,
        )

        target_crop = Crop(detection=target_detection, path="target.jpg")
        other_crop = Crop(detection=other_detection, path="other.jpg")

        session.add_all([target_crop, other_crop])
        session.commit()

        embedder = Mock()
        embedder.embed_batch.return_value = np.zeros((1, 512), dtype=np.float32)

        classifier = Mock()
        classifier.classify.return_value = ClassificationResult(
            identity="Hermann",
            similarity=0.95,
            matched_example_id=None,
            candidates=[],
        )

        service = ClassificationService(
            session,
            embedder,
            classifier,
        )

        summary = service.classify(asset_id=target_asset.id)

        assert summary.classified == 1

        result = session.query(CropClassification).one()

        assert result.crop_id == target_crop.id
        assert (
            session.query(Crop).filter_by(id=other_crop.id).one().classification is None
        )
