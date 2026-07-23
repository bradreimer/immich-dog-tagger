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
        assert summary.statuses == {
            "detected": 1,
        }
        assert summary.detections == 1
        assert summary.crops == 1
        assert summary.classifications == 1
        assert summary.unknown == 1
        assert summary.low_confidence == 1
        assert summary.pending_download == 0
        assert summary.pending_detection == 0
        assert summary.pending_classification == 0


def test_health_reports_asset_status_counts(engine):
    from sqlalchemy.orm import Session

    from immich_dog_tagger.models import Asset
    from immich_dog_tagger.services.health import HealthService
    from immich_dog_tagger.status import AssetStatus

    with Session(engine) as session:
        session.add_all(
            [
                Asset(
                    immich_asset_id="asset-1",
                    checksum="checksum-1",
                    extension=".jpg",
                    status=AssetStatus.PENDING,
                ),
                Asset(
                    immich_asset_id="asset-2",
                    checksum="checksum-2",
                    extension=".jpg",
                    status=AssetStatus.DOWNLOADED,
                ),
                Asset(
                    immich_asset_id="asset-3",
                    checksum="checksum-3",
                    extension=".jpg",
                    status=AssetStatus.DETECTED,
                ),
                Asset(
                    immich_asset_id="asset-4",
                    checksum="checksum-4",
                    extension=".jpg",
                    status=AssetStatus.DOWNLOAD_FAILED,
                ),
                Asset(
                    immich_asset_id="asset-5",
                    checksum="checksum-5",
                    extension=".jpg",
                    status=AssetStatus.DETECTION_FAILED,
                ),
                Asset(
                    immich_asset_id="asset-6",
                    checksum="checksum-6",
                    extension=".jpg",
                    status=AssetStatus.CLASSIFICATION_FAILED,
                ),
            ]
        )

        session.commit()

        summary = HealthService(session).summary()

        assert summary.assets == 6
        assert summary.statuses == {
            "pending": 1,
            "downloaded": 1,
            "detected": 1,
            "download_failed": 1,
            "detection_failed": 1,
            "classification_failed": 1,
        }
        assert summary.download_failed == 1
        assert summary.detection_failed == 1
        assert summary.classification_failed == 1
