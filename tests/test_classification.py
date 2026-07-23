import numpy as np
from sqlalchemy.orm import Session
from immich_dog_tagger.classifier import ClassificationResult
from immich_dog_tagger.services.classification import ClassificationService
from immich_dog_tagger.models import (
    Asset,
    ClassificationSources,
    Crop,
    CropClassification,
    Detection,
)


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
            confidence=0.95,
            matched_example_id=42,
        )

        service = ClassificationService(
            session,
            embedder,
            classifier,
        )

        summary = service.classify_pending()

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

        summary = service.classify_pending()

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
            confidence=0.95,
            matched_example_id=42,
        )

        service = ClassificationService(
            session,
            embedder,
            classifier,
        )

        summary = service.classify_pending(
            force=True,
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
            confidence=0.95,
            matched_example_id=None,
        )

        service = ClassificationService(
            session,
            embedder,
            classifier,
        )

        summary = service.classify_pending(
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
            confidence=0.12,
            matched_example_id=None,
        )

        service = ClassificationService(
            session,
            embedder,
            classifier,
        )

        summary = service.classify_pending()

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
            confidence=0.95,
            matched_example_id=None,
        )

        service = ClassificationService(
            session,
            embedder,
            classifier,
        )

        summary = service.classify_pending()

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
            confidence=0.95,
            matched_example_id=42,
        )

        service = ClassificationService(
            session,
            embedder,
            classifier,
        )

        service.reclassify_pending(
            threshold=0.80,
        )

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
            confidence=0.5,
            matched_example_id=None,
        )

        service = ClassificationService(
            session,
            embedder,
            classifier,
        )

        service.classify_pending(
            threshold=0.65,
        )

        classifier.classify.assert_called_once()

        assert classifier.classify.call_args.kwargs["threshold"] == 0.65
