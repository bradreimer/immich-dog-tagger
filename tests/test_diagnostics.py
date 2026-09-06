"""Tests for the /diagnostics endpoint."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import Mock

from sqlalchemy.orm import Session

from immich_dog_tagger.api.dependencies import get_asset_repair_service, get_config
from immich_dog_tagger.enums import (
    AssetStatus,
    PipelineJobStatus,
    PipelineOperation,
    ReviewActions,
)
from immich_dog_tagger.models import (
    Asset,
    Crop,
    CropClassification,
    Detection,
    ReviewAction,
)
from immich_dog_tagger.services.job_recovery import STUCK_JOB_IDLE_THRESHOLD
from immich_dog_tagger.services.jobs import PipelineJobService


def test_diagnostics_endpoint_returns_expected_shape(api_client, monkeypatch, tmp_path):
    from immich_dog_tagger.config import Config

    fake_config = Config(
        immich_url="http://localhost",
        immich_api_key="test",
        state_dir=tmp_path / "state",
        cache_dir=tmp_path / "cache",
        yolo_model=tmp_path / "yolo11n.pt",
        crop_padding=0.1,
    )

    api_client.app.dependency_overrides[get_config] = lambda: fake_config

    response = api_client.get("/diagnostics")
    assert response.status_code == 200

    data = response.json()
    assert "db" in data
    assert "scheduler" in data
    assert "jobs" in data
    assert "backup" in data
    assert "derived_data" in data
    assert "stale_detections" in data
    assert data["stale_detections"]["healthy"] is True
    assert data["stale_detections"]["flagged"] == 0
    assert data["stale_detections"]["reviewed_at_risk"] == 0


def test_diagnostics_backup_section_reports_no_backup_when_empty(
    api_client, monkeypatch, tmp_path
):
    from immich_dog_tagger.config import Config

    fake_config = Config(
        immich_url="http://localhost",
        immich_api_key="test",
        state_dir=tmp_path / "state",
        cache_dir=tmp_path / "cache",
        yolo_model=tmp_path / "yolo11n.pt",
        crop_padding=0.1,
    )
    api_client.app.dependency_overrides[get_config] = lambda: fake_config

    response = api_client.get("/diagnostics")
    data = response.json()
    assert data["backup"]["has_backup"] is False
    assert data["backup"]["last_backup_at"] is None


def test_diagnostics_derived_data_healthy_on_empty_db(
    api_client, monkeypatch, tmp_path
):
    from immich_dog_tagger.config import Config

    fake_config = Config(
        immich_url="http://localhost",
        immich_api_key="test",
        state_dir=tmp_path / "state",
        cache_dir=tmp_path / "cache",
        yolo_model=tmp_path / "yolo11n.pt",
        crop_padding=0.1,
    )
    api_client.app.dependency_overrides[get_config] = lambda: fake_config

    response = api_client.get("/diagnostics")
    data = response.json()
    assert data["derived_data"]["healthy"] is True
    assert data["derived_data"]["total_missing"] == 0


def _fake_config(tmp_path):
    from immich_dog_tagger.config import Config

    return Config(
        immich_url="http://localhost",
        immich_api_key="test",
        state_dir=tmp_path / "state",
        cache_dir=tmp_path / "cache",
        yolo_model=tmp_path / "yolo11n.pt",
        crop_padding=0.1,
    )


def test_diagnostics_does_not_report_an_active_job_as_stuck(
    api_client, engine, tmp_path
):
    """Issue #134: starting a job must not raise the stuck-job warning."""

    api_client.app.dependency_overrides[get_config] = lambda: _fake_config(tmp_path)

    with Session(engine) as session:
        service = PipelineJobService(session)
        job = service.create_job(operation=PipelineOperation.SCAN)
        service.start_job(job)

        # A second job waiting its turn behind the running one is normal too.
        service.create_job(operation=PipelineOperation.SYNC)

    data = api_client.get("/diagnostics").json()

    assert data["jobs"]["stuck"] == []
    assert data["jobs"]["counts"][PipelineJobStatus.RUNNING.value] == 1
    assert (
        data["jobs"]["stuck_threshold_seconds"]
        == STUCK_JOB_IDLE_THRESHOLD.total_seconds()
    )


def test_diagnostics_reports_a_job_that_stopped_making_progress(
    api_client, engine, tmp_path
):
    api_client.app.dependency_overrides[get_config] = lambda: _fake_config(tmp_path)

    with Session(engine) as session:
        service = PipelineJobService(session)
        job = service.create_job(operation=PipelineOperation.DETECT)
        service.start_job(job)

        job.heartbeat_at = (
            job.heartbeat_at - STUCK_JOB_IDLE_THRESHOLD - timedelta(minutes=5)
        )
        session.commit()
        job_id = job.id

    data = api_client.get("/diagnostics").json()

    assert [entry["id"] for entry in data["jobs"]["stuck"]] == [job_id]

    entry = data["jobs"]["stuck"][0]
    assert entry["operation"] == PipelineOperation.DETECT.value
    assert entry["status"] == PipelineJobStatus.RUNNING.value
    assert entry["idle_seconds"] >= STUCK_JOB_IDLE_THRESHOLD.total_seconds()
    assert entry["last_activity_at"] is not None


def _add_flagged_reviewed_asset(engine) -> None:
    with Session(engine) as session:
        asset = Asset(
            immich_asset_id="asset-1",
            checksum="abc",
            extension=".jpg",
            status=AssetStatus.DETECTED,
            exif_width=4032,
            exif_height=3024,
            exif_orientation=6,
        )
        session.add(asset)
        session.flush()

        detection = Detection(
            asset_id=asset.id, label="dog", confidence=0.9, x1=0, y1=0, x2=3500, y2=100
        )
        session.add(detection)
        session.flush()

        crop = Crop(detection_id=detection.id, path="crop.jpg")
        session.add(crop)
        session.flush()

        classification = CropClassification(
            crop_id=crop.id, identity="Rex", confidence=0.8
        )
        session.add(classification)
        session.flush()

        session.add(
            ReviewAction(
                classification_id=classification.id,
                action=ReviewActions.CORRECT,
                identity="Rex",
            )
        )
        session.commit()


def test_diagnostics_reports_flagged_stale_detection(api_client, engine):
    _add_flagged_reviewed_asset(engine)

    data = api_client.get("/diagnostics").json()

    assert data["stale_detections"]["healthy"] is False
    assert data["stale_detections"]["flagged"] == 1
    assert data["stale_detections"]["reviewed_at_risk"] == 1


def test_repair_stale_detections_endpoint_skips_reviewed_by_default(api_client, engine):
    _add_flagged_reviewed_asset(engine)

    mock_repair_service = Mock()
    api_client.app.dependency_overrides[get_asset_repair_service] = lambda: (
        mock_repair_service
    )

    response = api_client.post("/diagnostics/stale-detections/repair")
    assert response.status_code == 200

    data = response.json()
    assert data == {"repaired": 0, "skipped_reviewed": 1, "failed": 0}
    mock_repair_service.repair.assert_not_called()


def test_repair_stale_detections_endpoint_include_reviewed_opt_in(api_client, engine):
    _add_flagged_reviewed_asset(engine)

    mock_repair_service = Mock()
    api_client.app.dependency_overrides[get_asset_repair_service] = lambda: (
        mock_repair_service
    )

    response = api_client.post(
        "/diagnostics/stale-detections/repair",
        params={"include_reviewed": True},
    )
    assert response.status_code == 200

    data = response.json()
    assert data == {"repaired": 1, "skipped_reviewed": 0, "failed": 0}
    mock_repair_service.repair.assert_called_once_with("asset-1")
