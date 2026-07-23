from sqlalchemy.orm import Session

from immich_dog_tagger.models import (
    Asset,
    Crop,
    Detection,
    EmbeddingExample,
    Identity,
)
from immich_dog_tagger.enums import AssetStatus, ClassificationSources, EmbeddingSources


def test_crop_relationship(engine):
    with Session(engine) as session:
        asset = Asset(
            immich_asset_id="abc123",
            checksum="xyz",
            extension=".jpg",
            status=AssetStatus.DETECTED,
        )

        session.add(asset)
        session.flush()

        detection = Detection(
            asset_id=asset.id,
            label="dog",
            confidence=0.95,
            x1=10,
            y1=20,
            x2=30,
            y2=40,
        )

        session.add(detection)
        session.flush()

        crop = Crop(
            detection_id=detection.id,
            path="crops/abc123_0.jpg",
        )

        session.add(crop)
        session.commit()

        result = session.query(Crop).one()

        assert result.path == "crops/abc123_0.jpg"
        assert result.detection.asset.immich_asset_id == "abc123"


def test_embedding_sources():
    assert EmbeddingSources.BOOTSTRAP == "bootstrap"
    assert EmbeddingSources.REVIEW == "review"
    assert EmbeddingSources.IMPORT == "import"


def test_classification_sources():
    assert ClassificationSources.AUTO == "auto"
    assert ClassificationSources.REVIEW == "review"


def test_embedding_source_enum_round_trip(engine):
    with Session(engine) as session:
        identity = Identity(
            name="Hermann",
        )

        example = EmbeddingExample(
            identity=identity,
            crop_path="example.jpg",
            embedding=b"123",
            source=EmbeddingSources.REVIEW,
        )

        session.add(example)
        session.commit()

        result = session.query(EmbeddingExample).one()

        assert result.source == EmbeddingSources.REVIEW
