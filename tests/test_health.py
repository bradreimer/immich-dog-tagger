from sqlalchemy.orm import Session

from immich_dog_tagger.models import (
    Asset,
    Crop,
    CropClassification,
    Detection,
)
from immich_dog_tagger.services.health import HealthService
from immich_dog_tagger.status import AssetStatus


def test_health_summary(engine):
    with Session(engine) as session:
        asset = Asset(
            immich_asset_id="asset1",
            checksum="checksum",
            extension=".jpg",
            status=AssetStatus.DETECTED,
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
            path="crop.jpg",
        )

        session.add(
            CropClassification(
                crop=crop,
                identity=None,
                confidence=0.5,
            )
        )

        session.add(asset)
        session.commit()

        service = HealthService(session)

        summary = service.summary()

        assert summary.assets == 1
        assert summary.detected == 1
        assert summary.detections == 1
        assert summary.crops == 1
        assert summary.classifications == 1
        assert summary.unknown == 1
        assert summary.low_confidence == 1
