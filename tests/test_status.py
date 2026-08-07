from sqlalchemy.orm import Session

from immich_dog_tagger.enums import AssetStatus, ReviewActions
from immich_dog_tagger.models import (
    Asset,
    Crop,
    CropClassification,
    Detection,
    EmbeddingExample,
    EmbeddingSources,
    Identity,
    ReviewAction,
)
from immich_dog_tagger.services.status import StatusService


def test_status_summary(engine):
    with Session(engine) as session:
        asset = Asset(
            immich_asset_id="asset1",
            checksum="abc",
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
            path="crop.jpg",
        )

        identity = Identity(
            name="Fibs",
        )

        example = EmbeddingExample(
            identity=identity,
            crop_path="example.jpg",
            embedding=b"123",
            source=EmbeddingSources.REVIEW,
        )

        classification = CropClassification(
            crop=crop,
            identity="Fibs",
            confidence=0.95,
        )

        session.add_all(
            [
                asset,
                detection,
                crop,
                identity,
                example,
                classification,
            ]
        )

        session.flush()

        session.add(
            ReviewAction(
                classification_id=classification.id,
                action=ReviewActions.CORRECT,
                identity="Fibs",
            )
        )

        session.commit()

        summary = StatusService(session).summary()

        assert summary.assets == 1
        assert summary.detections == 1
        assert summary.crops == 1
        assert summary.classifications == 1
        assert summary.identities == 1
        assert summary.examples == 1
        assert summary.examples_by_source == {
            "bootstrap": 0,
            "review": 1,
            "import": 0,
        }
        assert summary.review_actions_by_type == {
            "skip": 0,
            "correct": 1,
        }


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

        service = StatusService(session)

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

    from immich_dog_tagger.enums import AssetStatus
    from immich_dog_tagger.models import Asset
    from immich_dog_tagger.services.status import StatusService

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

        summary = StatusService(session).summary()

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


def test_pipeline_plan_empty_database(engine):
    with Session(engine) as session:
        service = StatusService(session)

        plan = service.pipeline_plan()

    assert plan.pending_download == 0
    assert plan.pending_detection == 0
    assert plan.pending_classification == 0
