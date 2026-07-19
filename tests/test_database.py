from pathlib import Path

from sqlalchemy.orm import Session

from immich_dog_tagger.models import (
    Asset,
    EmbeddingExample,
    Identity,
    Crop,
    CropClassification,
    Detection,
)
from immich_dog_tagger.status import AssetStatus


def test_database_creation(engine, tmp_path: Path):
    assert (tmp_path / "state.db").exists()

    with Session(engine) as session:
        asset = Asset(
            immich_asset_id="abc123",
            checksum="xyz",
            extension=".jpg",
        )
        session.add(asset)
        session.commit()

        result = session.query(Asset).one()

        assert result.immich_asset_id == "abc123"
        assert result.checksum == "xyz"
        assert result.status is AssetStatus.PENDING

        identity = Identity(
            name="Hermann",
        )

        session.add(identity)
        session.commit()

        embedding = EmbeddingExample(
            identity_id=identity.id,
            crop_path="crops/hermann_001.jpg",
            embedding=b"\x01\x02\x03",
        )

        session.add(embedding)
        session.commit()

        result = session.query(EmbeddingExample).one()

        assert result.crop_path == ("crops/hermann_001.jpg")

        assert result.embedding == (b"\x01\x02\x03")

        assert result.identity.name == ("Hermann")


def test_crop_classification_persistence(engine):
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

        classification = CropClassification(
            crop=crop,
            identity="Hermann",
            confidence=0.95,
        )

        session.add(classification)
        session.commit()

        result = session.query(CropClassification).one()

        assert result.identity == "Hermann"
        assert result.crop.path == "test.jpg"
        assert result.crop.detection.label == "dog"
