from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from immich_dog_tagger.detector import DetectionResult
from immich_dog_tagger.enums import AssetStatus
from immich_dog_tagger.models import Asset, Crop, Detection
from immich_dog_tagger.services.detection import BATCH_SIZE, DetectionService


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


def test_detection_creates_one_crop_per_species_from_same_photo(
    engine,
    tmp_path,
):
    # DT-1110 acceptance criterion 2: a single photo containing both a dog
    # and a cat produces the union of both detections -- two crops, each
    # tagged with its own species -- not just the dog, and not merged into
    # one crop.
    class MixedDetector:
        def detect(self, image_path):
            return [
                DetectionResult(label="dog", confidence=0.95, x1=0, y1=0, x2=50, y2=50),
                DetectionResult(
                    label="cat", confidence=0.90, x1=60, y1=60, x2=100, y2=100
                ),
            ]

    class MixedCropWriter:
        def write(self, image_path, asset_id, detections):
            crops = []
            for index, detection in enumerate(detections):
                path = tmp_path / f"{asset_id}_{index}.jpg"
                path.write_bytes(b"fake crop")
                crops.append((index, path))
            return crops

    with Session(engine) as session:
        asset = Asset(
            immich_asset_id="mixed-asset",
            checksum="xyz",
            extension=".jpg",
            status=AssetStatus.DOWNLOADED,
        )
        session.add(asset)
        session.commit()

        service = DetectionService(
            MixedDetector(),
            session,
            tmp_path,
            crop_writer=MixedCropWriter(),
        )

        summary = service.run()

        assert summary.processed == 1
        assert summary.detections == 2
        assert summary.dogs == 1
        assert summary.cats == 1

        crops = session.query(Crop).order_by(Crop.id).all()

        assert len(crops) == 2
        assert crops[0].species == "dog"
        assert crops[1].species == "cat"


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


def test_detection_failure_is_enriched_with_asset_context(
    engine,
    tmp_path,
    caplog,
):
    # Regression test for issue #88: a bare exception message (e.g. a
    # Pillow error) gives no way to tell which asset caused a pipeline job
    # failure without reproducing it. The service should fold the asset id
    # and image path into the raised error and log a traceback.
    class FailingCropWriter:
        def write(self, image_path, asset_id, detections):
            raise ValueError("boom")

    with Session(engine) as session:
        asset = Asset(
            immich_asset_id="broken-asset",
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
            crop_writer=FailingCropWriter(),
        )

        with caplog.at_level("ERROR"), pytest.raises(RuntimeError) as excinfo:
            service.run()

        assert "boom" in str(excinfo.value)
        assert "broken-asset" in str(excinfo.value)
        assert "Detection failed for asset broken-asset" in caplog.text


def test_detection_deletes_cached_original_after_crop_writer_succeeds(
    engine,
    tmp_path,
):
    # Regression test for issue #93: once crops exist, nothing downstream
    # (embed/classify/sync) needs the original again -- keeping it around
    # forever wastes disk space proportional to the whole library instead
    # of what the app actually uses.
    class FakeCropWriter:
        def write(self, image_path, asset_id, detections):
            crop_path = tmp_path / f"{asset_id}_0.jpg"
            crop_path.write_bytes(b"fake crop")
            return [(0, crop_path)]

    with Session(engine) as session:
        asset = Asset(
            immich_asset_id="abc123",
            checksum="xyz",
            extension=".jpg",
            status=AssetStatus.DOWNLOADED,
        )
        session.add(asset)
        session.commit()

        original_path = asset.cache_path(tmp_path)
        original_path.write_bytes(b"original bytes")

        service = DetectionService(
            FakeDetector(),
            session,
            tmp_path,
            crop_writer=FakeCropWriter(),
        )

        summary = service.run()

        assert summary.processed == 1
        assert not original_path.exists()
        assert (tmp_path / "abc123_0.jpg").exists()


def test_detection_keeps_cached_original_without_crop_writer(
    engine,
    tmp_path,
):
    # No crop_writer means no crop stands in for the original, so there's
    # nothing to show for it if it's deleted -- leave it alone.
    with Session(engine) as session:
        asset = Asset(
            immich_asset_id="abc123",
            checksum="xyz",
            extension=".jpg",
            status=AssetStatus.DOWNLOADED,
        )
        session.add(asset)
        session.commit()

        original_path = asset.cache_path(tmp_path)
        original_path.write_bytes(b"original bytes")

        service = DetectionService(
            FakeDetector(),
            session,
            tmp_path,
        )

        summary = service.run()

        assert summary.processed == 1
        assert original_path.exists()


def test_detection_commits_in_batches_of_1000(
    engine,
    tmp_path,
):
    # Regression test for issue #104: a single commit at the end of the
    # whole run held state.db's write lock for the run's entire duration,
    # blocking every other reader for as long as the run took.
    total = BATCH_SIZE + 500

    with Session(engine) as session:
        assets = [
            Asset(
                immich_asset_id=f"asset-{index}",
                checksum=f"checksum-{index}",
                extension=".jpg",
                status=AssetStatus.DOWNLOADED,
            )
            for index in range(total)
        ]
        session.add_all(assets)
        session.commit()

        service = DetectionService(
            FakeDetector(),
            session,
            tmp_path,
        )

        commit_calls = []
        original_commit = session.commit

        def counting_commit():
            commit_calls.append(1)
            original_commit()

        session.commit = counting_commit

        summary = service.run()

        assert summary.processed == total
        # One commit at the BATCH_SIZE boundary, one final commit for the
        # remaining 500 -- proves the loop doesn't hold everything for a
        # single commit at the end.
        assert len(commit_calls) == 2
        assert session.query(Detection).count() == total


def test_detection_failure_leaves_only_prior_batches_committed(
    engine,
    tmp_path,
):
    # Regression test for issue #104: a failure partway through a run must
    # not discard batches already committed, the same guarantee issue #99
    # established for scan/download.
    total = BATCH_SIZE + 500
    fail_at = BATCH_SIZE + 200

    class FlakyDetector:
        def __init__(self):
            self._calls = 0

        def detect(self, image_path):
            self._calls += 1

            if self._calls == fail_at:
                raise ValueError("simulated failure")

            return FakeDetector().detect(image_path)

    with Session(engine) as session:
        assets = [
            Asset(
                immich_asset_id=f"asset-{index}",
                checksum=f"checksum-{index}",
                extension=".jpg",
                status=AssetStatus.DOWNLOADED,
            )
            for index in range(total)
        ]
        session.add_all(assets)
        session.commit()

        service = DetectionService(
            FlakyDetector(),
            session,
            tmp_path,
        )

        with pytest.raises(RuntimeError, match="simulated failure"):
            service.run()

    with Session(engine) as verify_session:
        # Only the first full batch (1000) was committed; the failure at
        # 1200 happened inside the still-uncommitted second batch, which
        # was never flushed to disk.
        assert verify_session.query(Detection).count() == BATCH_SIZE
