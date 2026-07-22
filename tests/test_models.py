from sqlalchemy.orm import Session

from immich_dog_tagger.models import (
    Asset,
    Crop,
    Detection,
    EmbeddingSources,
)
from immich_dog_tagger.status import AssetStatus


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
