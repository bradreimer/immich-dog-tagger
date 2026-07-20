import numpy as np

from immich_dog_tagger.classifier import ClassificationResult
from immich_dog_tagger.classification import ClassificationService
from sqlalchemy.orm import Session
from immich_dog_tagger.models import (
    Asset,
    Crop,
    CropClassification,
    Detection,
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
        embedder.embed.return_value = np.zeros(
            512,
            dtype=np.float32,
        )

        classifier = Mock()
        classifier.classify.return_value = ClassificationResult(
            identity="Hermann",
            confidence=0.95,
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
        embedder.embed.return_value = np.zeros(
            512,
            dtype=np.float32,
        )

        classifier = Mock()
        classifier.classify.return_value = ClassificationResult(
            identity=None,
            confidence=0.12,
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
