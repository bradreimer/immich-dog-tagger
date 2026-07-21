import numpy as np
from sqlalchemy.orm import Session
from immich_dog_tagger.classifier import ClassificationResult
from immich_dog_tagger.services.classification import ClassificationService
from immich_dog_tagger.models import (
    Asset,
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
        assert result.matched_example_id == 42
        assert result.crop.id == crop.id


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


# def test_classification_service_updates_existing_classification(engine):
#     from unittest.mock import Mock

#     with Session(engine) as session:
#         crop = Crop(
#             detection_id=1,
#             path="test.jpg",
#         )

#         session.add(crop)
#         session.flush()

#         existing = CropClassification(
#             crop=crop,
#             identity=None,
#             confidence=0.2,
#         )

#         session.add(existing)
#         session.commit()

#         embedder = Mock()
#         embedder.embed_batch.return_value = np.array(
#             [[1, 0, 0]],
#             dtype=np.float32,
#         )

#         classifier = Mock()
#         classifier.classify.return_value = ClassificationResult(
#             identity="Hermann",
#             confidence=0.95,
#             matched_example_id=42,
#         )

#         service = ClassificationService(
#             session,
#             embedder,
#             classifier,
#         )

#         service.reclassify_pending(
#             threshold=0.80,
#         )

#         result = session.query(CropClassification).one()

#         assert result.identity == "Hermann"
#         assert result.confidence == 0.95
#         assert result.matched_example_id == 42
