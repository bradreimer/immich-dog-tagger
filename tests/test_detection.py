from sqlalchemy.orm import Session
from pathlib import Path
from immich_dog_tagger.services.detection import DetectionService
from immich_dog_tagger.detector import DetectionResult
from immich_dog_tagger.models import Asset, Crop, Detection
from immich_dog_tagger.enums import AssetStatus


class FakeDetector:
    def detect(self, image_path):
        return [
            DetectionResult(
                label="dog",
                confidence=0.99,
                x1=10,
                y1=20,
                x2=100,
                y2=200,
            )
        ]


def test_detection_creates_record(
    engine,
    tmp_path,
):
    with Session(engine) as session:
        asset = Asset(
            immich_asset_id="abc123",
            checksum="xyz",
            extension=".jpg",
            status=AssetStatus.DOWNLOADED,
        )
        session.add(asset)
        session.commit()

        service = DetectionService(
            FakeDetector(),
            session,
            tmp_path,
        )

        summary = service.run()

        assert summary.processed == 1
        assert summary.detections == 1
        assert summary.dogs == 1

        detection = session.query(Detection).one()

        assert detection.label == "dog"

        session.refresh(asset)

        assert asset.status is AssetStatus.DETECTED


def test_detection_skips_video_assets(engine):
    with Session(engine) as session:
        asset = Asset(
            immich_asset_id="abc123",
            checksum="xyz",
            extension=".mp4",
            status=AssetStatus.DOWNLOADED,
        )
        session.add(asset)
        session.commit()

        service = DetectionService(
            FakeDetector(),
            session,
            Path("/tmp"),
        )

        summary = service.run()

        assert summary.processed == 0
        assert summary.detections == 0
        assert summary.dogs == 0

        result = session.query(Detection).all()

        assert len(result) == 0


def test_detection_skips_existing_detections_by_default(
    engine,
    tmp_path,
):
    with Session(engine) as session:
        asset = Asset(
            immich_asset_id="abc123",
            checksum="xyz",
            extension=".jpg",
            status=AssetStatus.DOWNLOADED,
        )
        session.add(asset)
        session.commit()

        existing = Detection(
            asset_id=asset.id,
            label="dog",
            confidence=0.95,
            x1=1,
            y1=2,
            x2=50,
            y2=60,
        )
        session.add(existing)
        session.commit()

        service = DetectionService(
            FakeDetector(),
            session,
            tmp_path,
        )

        summary = service.run()

        assert summary.processed == 0
        assert summary.detections == 0
        assert summary.dogs == 0

        detections = session.query(Detection).all()

        assert len(detections) == 1


def test_detection_force_reprocesses_existing_detections(
    engine,
    tmp_path,
):
    with Session(engine) as session:
        asset = Asset(
            immich_asset_id="abc123",
            checksum="xyz",
            extension=".jpg",
            status=AssetStatus.DOWNLOADED,
        )
        session.add(asset)
        session.commit()

        existing = Detection(
            asset_id=asset.id,
            label="cat",
            confidence=0.95,
            x1=1,
            y1=2,
            x2=50,
            y2=60,
        )
        session.add(existing)
        session.commit()

        service = DetectionService(
            FakeDetector(),
            session,
            tmp_path,
        )

        summary = service.run(
            force=True,
        )

        assert summary.processed == 1
        assert summary.detections == 1
        assert summary.dogs == 1

        detections = session.query(Detection).all()

        assert len(detections) == 1
        assert detections[0].label == "dog"


def test_detection_respects_limit(
    engine,
    tmp_path,
):
    with Session(engine) as session:
        assets = [
            Asset(
                immich_asset_id=f"asset-{index}",
                checksum=f"checksum-{index}",
                extension=".jpg",
                status=AssetStatus.DOWNLOADED,
            )
            for index in range(5)
        ]

        session.add_all(assets)
        session.commit()

        service = DetectionService(
            FakeDetector(),
            session,
            tmp_path,
        )

        summary = service.run(
            limit=2,
        )

        assert summary.processed == 2
        assert summary.detections == 2
        assert summary.dogs == 2

        detections = session.query(Detection).all()

        assert len(detections) == 2


def test_detection_force_replaces_existing_crop(
    engine,
    tmp_path,
):
    class FakeCropWriter:
        def write(
            self,
            image_path,
            asset_id,
            detections,
        ):
            new_crop = tmp_path / "new-crop.jpg"
            new_crop.write_bytes(b"new crop")

            return [
                (0, new_crop),
            ]

    old_crop = tmp_path / "old-crop.jpg"
    old_crop.write_bytes(b"old crop")

    with Session(engine) as session:
        asset = Asset(
            immich_asset_id="abc123",
            checksum="xyz",
            extension=".jpg",
            status=AssetStatus.DETECTED,
        )

        session.add(asset)
        session.commit()

        detection = Detection(
            asset_id=asset.id,
            label="cat",
            confidence=0.9,
            x1=1,
            y1=2,
            x2=50,
            y2=60,
        )

        session.add(detection)
        session.flush()

        session.add(
            Crop(
                detection_id=detection.id,
                path=str(old_crop),
            )
        )

        session.commit()

        service = DetectionService(
            FakeDetector(),
            session,
            tmp_path,
            crop_writer=FakeCropWriter(),
        )

        summary = service.run(
            force=True,
        )

        assert summary.processed == 1
        assert summary.detections == 1

        assert not old_crop.exists()

        crops = session.query(Crop).all()

        assert len(crops) == 1
        assert crops[0].path != str(old_crop)
