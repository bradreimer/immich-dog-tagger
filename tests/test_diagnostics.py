"""Tests for the /diagnostics endpoint."""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy.orm import Session

from immich_dog_tagger.api.dependencies import get_config
from immich_dog_tagger.enums import PipelineJobStatus, PipelineOperation
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
