"""
Issue #390: Photo Lookup's "Look harder" -- Repair for one photo, with the
open-vocabulary Grounding DINO detector in place of YOLO.
"""

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import Mock

import numpy as np
import pytest
import torch
from PIL import Image
from sqlalchemy import text
from sqlalchemy.orm import Session

from immich_dog_tagger.classifier import ClassificationResult
from immich_dog_tagger.config import Config
from immich_dog_tagger.detector import DetectionResult
from immich_dog_tagger.enums import (
    AssetStatus,
    DetectorKind,
    PipelineJobStatus,
    PipelineOperation,
    Species,
)
from immich_dog_tagger.grounding_dino_detector import (
    GroundingDinoDetector,
    species_for_label,
)
from immich_dog_tagger.immich import ImmichAsset, ImmichGetAssetError
from immich_dog_tagger.models import Asset, Crop, Detection
from immich_dog_tagger.services.asset_repair import AssetRepairService
from immich_dog_tagger.services.detection import DetectionService
from immich_dog_tagger.services.job_execution import create_pipeline_job_runner
from immich_dog_tagger.services.jobs import PipelineJobService
from immich_dog_tagger.services.schedules import PipelineScheduleService


class FakeLookHarderDetector:
    kind = DetectorKind.GROUNDING_DINO

    def __init__(self, results=None):
        self.results = (
            results
            if results is not None
            else [
                DetectionResult(label="dog", confidence=0.7, x1=5, y1=5, x2=50, y2=60)
            ]
        )

    def detect(self, image_path, **kwargs):
        return self.results


class FakeYoloDetector:
    def detect(self, image_path, **kwargs):
        return [DetectionResult(label="dog", confidence=0.9, x1=1, y1=1, x2=9, y2=9)]


class FakeCropWriter:
    def __init__(self, crop_dir, *args, **kwargs):
        self.crop_dir = Path(crop_dir)

    def write(self, image_path, asset_id, detections, **kwargs):
        self.crop_dir.mkdir(parents=True, exist_ok=True)
        results = []

        for index, _ in enumerate(detections):
            crop_path = self.crop_dir / f"{asset_id}_{index}.jpg"
            crop_path.write_bytes(b"crop")
            results.append((index, crop_path))

        return results


class FakeBatchEmbedder:
    MODEL_ID = "fake:test"

    def embed_batch(self, paths):
        return np.zeros((len(paths), 3), dtype=np.float32)


# --- GroundingDinoDetector ---------------------------------------------------


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("dog", Species.DOG),
        ("a dog", Species.DOG),
        ("Cat", Species.CAT),
        ("a cat", Species.CAT),
        ("", None),
        ("doghouse", None),
    ],
)
def test_species_for_label(label, expected):
    assert species_for_label(label) == expected


class _FakeInputs(dict):
    def __init__(self):
        super().__init__(pixel_values=torch.zeros(1))
        self.input_ids = torch.zeros(1)

    def to(self, device):
        return self


class _FakeProcessor:
    def __init__(self, result):
        self.result = result
        self.prompt = None

    def __call__(self, images, text, return_tensors):
        self.prompt = text
        self.image_size = images.size
        return _FakeInputs()

    def post_process_grounded_object_detection(self, outputs, input_ids, **kwargs):
        self.target_sizes = kwargs["target_sizes"]
        return [self.result]


def _detector_with(tmp_path, result, size=(200, 100)):
    image_path = tmp_path / "photo.jpg"
    Image.new("RGB", size, "white").save(image_path)

    detector = GroundingDinoDetector("unused-model-id", device="cpu")
    processor = _FakeProcessor(result)
    detector._processor = processor
    detector._model = lambda **inputs: object()

    return detector, processor, image_path


def test_grounding_dino_maps_labels_suppresses_duplicates_and_clamps(tmp_path):
    detector, processor, image_path = _detector_with(
        tmp_path,
        {
            "boxes": torch.tensor(
                [
                    [10.0, 10.0, 90.0, 80.0],
                    # Same animal matched by the other phrase: suppressed.
                    [11.0, 11.0, 91.0, 81.0],
                    # Spills past the image edge: clamped.
                    [-5.0, 20.0, 250.0, 120.0],
                    [100.0, 10.0, 150.0, 40.0],
                ]
            ),
            "scores": torch.tensor([0.8, 0.6, 0.5, 0.4]),
            "text_labels": ["dog", "cat", "a cat", "table"],
        },
    )

    detections = detector.detect(str(image_path))

    assert processor.prompt == "a dog. a cat."
    # (height, width) of the open_upright()-decoded image.
    assert processor.target_sizes == [(100, 200)]
    assert detector.kind == DetectorKind.GROUNDING_DINO
    assert detections == [
        DetectionResult(
            label="dog", confidence=pytest.approx(0.8), x1=10, y1=10, x2=90, y2=80
        ),
        DetectionResult(
            label="cat", confidence=pytest.approx(0.5), x1=0, y1=20, x2=200, y2=100
        ),
    ]


def test_grounding_dino_returns_nothing_for_no_boxes(tmp_path):
    detector, _, image_path = _detector_with(
        tmp_path,
        {
            "boxes": torch.zeros((0, 4)),
            "scores": torch.zeros(0),
            "text_labels": [],
        },
    )

    assert detector.detect(str(image_path)) == []


def test_grounding_dino_does_not_load_model_until_first_detect():
    detector = GroundingDinoDetector("unused-model-id")

    assert detector._model is None
    assert detector._processor is None


# --- Detection provenance ----------------------------------------------------


def _downloaded_asset(session, tmp_path, immich_asset_id="target", **kwargs):
    asset = Asset(
        immich_asset_id=immich_asset_id,
        checksum="xyz",
        extension=".jpg",
        status=kwargs.pop("status", AssetStatus.DOWNLOADED),
        **kwargs,
    )
    session.add(asset)
    session.commit()
    asset.cache_path(tmp_path).write_bytes(b"data")
    return asset


def test_detection_records_detector_kind(engine, tmp_path):
    with Session(engine) as session:
        _downloaded_asset(session, tmp_path)

        DetectionService(FakeLookHarderDetector(), session, tmp_path).run()

        assert session.query(Detection).one().detector == "grounding_dino"


def test_detection_without_kind_records_yolo(engine, tmp_path):
    with Session(engine) as session:
        _downloaded_asset(session, tmp_path)

        DetectionService(FakeYoloDetector(), session, tmp_path).run()

        assert session.query(Detection).one().detector == "yolo"


def test_batch_force_detect_keeps_look_harder_detections(engine, tmp_path):
    with Session(engine) as session:
        looked_at = _downloaded_asset(
            session, tmp_path, "looked-at", status=AssetStatus.DETECTED
        )
        session.add(
            Detection(
                asset=looked_at,
                label="dog",
                confidence=0.7,
                x1=5,
                y1=5,
                x2=50,
                y2=60,
                detector="grounding_dino",
            )
        )
        plain = _downloaded_asset(
            session, tmp_path, "plain", status=AssetStatus.DETECTED
        )
        session.add(
            Detection(asset=plain, label="dog", confidence=0.5, x1=0, y1=0, x2=2, y2=2)
        )
        session.commit()

        summary = DetectionService(FakeYoloDetector(), session, tmp_path).run(
            force=True
        )

        assert summary.processed == 1
        kept = session.query(Detection).filter_by(asset_id=looked_at.id).one()
        assert kept.detector == "grounding_dino"
        assert kept.x2 == 50


def test_per_photo_detect_replaces_look_harder_detections(engine, tmp_path):
    with Session(engine) as session:
        asset = _downloaded_asset(session, tmp_path, status=AssetStatus.DETECTED)
        session.add(
            Detection(
                asset=asset,
                label="dog",
                confidence=0.7,
                x1=5,
                y1=5,
                x2=50,
                y2=60,
                detector="grounding_dino",
            )
        )
        session.commit()

        DetectionService(FakeYoloDetector(), session, tmp_path).run(
            force=True, asset_id=asset.id
        )

        assert session.query(Detection).one().detector == "yolo"


# --- AssetRepairService action naming ------------------------------------------


def test_repair_failure_names_the_action(engine, tmp_path):
    with Session(engine) as session:
        _downloaded_asset(session, tmp_path)

        downloader = Mock()
        downloader.client.get_asset.side_effect = ImmichGetAssetError("boom")

        service = AssetRepairService(
            session,
            downloader,
            Mock(),
            Mock(),
            action="Look harder",
        )

        result = service.repair("target")

        assert result.succeeded is False
        assert result.message.startswith("Look harder failed:")


# --- look_harder job -----------------------------------------------------------


def _config(tmp_path):
    return Config(
        immich_url="http://immich.test",
        immich_api_key="key",
        state_dir=tmp_path / "state",
        cache_dir=tmp_path / "cache",
        yolo_model=tmp_path / "yolo11m.pt",
        crop_padding=0.15,
    )


def _patch_look_harder(monkeypatch, detector, client):
    module = "immich_dog_tagger.services.job_execution"
    monkeypatch.setattr(f"{module}.get_look_harder_detector", lambda: detector)
    monkeypatch.setattr(f"{module}._create_client", lambda config, account: client)
    monkeypatch.setattr(f"{module}.CropWriter", FakeCropWriter)
    monkeypatch.setattr(f"{module}.get_embedder", FakeBatchEmbedder)

    classifier = Mock()
    classifier.classify.return_value = ClassificationResult(
        identity="Hermann",
        similarity=0.95,
        matched_example_id=None,
        candidates=[],
    )
    monkeypatch.setattr(f"{module}.IdentityClassifier", lambda *a, **k: classifier)


def _fake_client():
    client = Mock()
    client.download_asset.return_value = b"image data"
    client.get_asset.return_value = ImmichAsset(
        id="target",
        filename="target.jpg",
        checksum="xyz",
        captured_at=datetime(2024, 5, 1, 12, 0, tzinfo=UTC),
    )
    return client


def _seed_yolo_asset(session):
    asset = Asset(
        immich_asset_id="target",
        checksum="xyz",
        extension=".jpg",
        status=AssetStatus.CLASSIFIED,
    )
    session.add(asset)
    session.add(
        Detection(asset=asset, label="person", confidence=0.4, x1=0, y1=0, x2=3, y2=3)
    )
    session.commit()
    return asset


def _run_look_harder(session, config, target="target"):
    job = PipelineJobService(session).create_job(
        operation=PipelineOperation.LOOK_HARDER,
        target_immich_asset_id=target,
    )
    runner = create_pipeline_job_runner(session, config)

    try:
        runner.run_job(job.id)
    except RuntimeError:
        pass

    session.refresh(job)
    return job


def test_look_harder_job_replaces_detections_with_grounding_dino(
    engine, tmp_path, monkeypatch
):
    config = _config(tmp_path)
    _patch_look_harder(monkeypatch, FakeLookHarderDetector(), _fake_client())

    with Session(engine) as session:
        asset = _seed_yolo_asset(session)

        job = _run_look_harder(session, config)

        assert job.status == PipelineJobStatus.COMPLETED
        assert job.progress_message == (
            "Look harder found 1 dog(s) and 0 cat(s); 1 classified."
        )

        detection = session.query(Detection).filter_by(asset_id=asset.id).one()
        assert detection.detector == "grounding_dino"
        assert detection.label == "dog"
        crop = session.query(Crop).one()
        assert crop.classification.identity == "Hermann"


def test_look_harder_job_reports_when_nothing_found(engine, tmp_path, monkeypatch):
    config = _config(tmp_path)
    _patch_look_harder(monkeypatch, FakeLookHarderDetector(results=[]), _fake_client())

    with Session(engine) as session:
        asset = _seed_yolo_asset(session)

        job = _run_look_harder(session, config)

        assert job.status == PipelineJobStatus.COMPLETED
        assert (
            job.progress_message == "Look harder found no dogs or cats in this photo."
        )
        assert session.query(Detection).filter_by(asset_id=asset.id).count() == 0


def test_look_harder_job_fails_when_repair_fails(engine, tmp_path, monkeypatch):
    config = _config(tmp_path)
    client = _fake_client()
    client.get_asset.side_effect = ImmichGetAssetError("unreachable")
    _patch_look_harder(monkeypatch, FakeLookHarderDetector(), client)

    with Session(engine) as session:
        asset = _seed_yolo_asset(session)

        job = _run_look_harder(session, config)

        assert job.status == PipelineJobStatus.FAILED
        assert "Look harder failed" in job.error_message
        # Nothing destructive happened: the old detection is still there.
        assert session.query(Detection).filter_by(asset_id=asset.id).count() == 1


def test_look_harder_job_without_target_fails(engine, tmp_path, monkeypatch):
    _patch_look_harder(monkeypatch, FakeLookHarderDetector(), _fake_client())

    with Session(engine) as session:
        job = PipelineJobService(session).create_job(
            operation=PipelineOperation.LOOK_HARDER
        )

        with pytest.raises(RuntimeError, match="no target photo"):
            create_pipeline_job_runner(session, _config(tmp_path)).run_job(job.id)

        session.refresh(job)
        assert job.status == PipelineJobStatus.FAILED


# --- Schedules -----------------------------------------------------------------


def test_schedule_rejects_look_harder(engine):
    with (
        Session(engine) as session,
        pytest.raises(ValueError, match="Look harder cannot be scheduled"),
    ):
        PipelineScheduleService(session).create_schedule(
            name="Nightly look harder",
            operation=PipelineOperation.LOOK_HARDER,
            expression="30 2 * * *",
            timezone_name="UTC",
        )


# --- Migration -----------------------------------------------------------------


def test_database_adds_detector_and_job_target_columns(tmp_path: Path):
    connection = sqlite3.connect(tmp_path / "state.db")
    # Pre-#390 shapes: no detections.detector, no pipeline_jobs.target_immich_asset_id.
    connection.execute(
        "CREATE TABLE detections ("
        "id INTEGER PRIMARY KEY, asset_id INTEGER, label VARCHAR NOT NULL, "
        "confidence FLOAT NOT NULL, x1 INTEGER NOT NULL, y1 INTEGER NOT NULL, "
        "x2 INTEGER NOT NULL, y2 INTEGER NOT NULL)"
    )
    connection.execute(
        "INSERT INTO detections (asset_id, label, confidence, x1, y1, x2, y2) "
        "VALUES (1, 'dog', 0.9, 1, 2, 3, 4)"
    )
    connection.execute(
        "CREATE TABLE pipeline_jobs ("
        "id INTEGER PRIMARY KEY, operation VARCHAR(32) NOT NULL, "
        "status VARCHAR(16) NOT NULL, progress_current INTEGER NOT NULL DEFAULT 0, "
        "progress_total INTEGER, progress_message VARCHAR(512), "
        "error_message VARCHAR(2048))"
    )
    connection.execute(
        "INSERT INTO pipeline_jobs (operation, status) VALUES ('scan', 'completed')"
    )
    connection.commit()
    connection.close()

    from immich_dog_tagger.database import create_database

    engine = create_database(tmp_path)

    with Session(engine) as session:
        detections = session.execute(
            text("SELECT label, x2, detector FROM detections")
        ).all()
        jobs = session.execute(
            text("SELECT operation, target_immich_asset_id FROM pipeline_jobs")
        ).all()

    assert detections == [("dog", 3, "yolo")]
    assert jobs == [("scan", None)]
