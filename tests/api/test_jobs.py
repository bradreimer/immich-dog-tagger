from sqlalchemy.orm import Session

from immich_dog_tagger.enums import PipelineJobStatus, PipelineOperation
from immich_dog_tagger.models import PipelineJob
from immich_dog_tagger.services.jobs import PipelineJobService


def test_jobs_list_returns_recent_jobs(api_client, engine):
    with Session(engine) as session:
        service = PipelineJobService(session)
        service.create_job(operation=PipelineOperation.SCAN)
        service.create_job(operation=PipelineOperation.CLASSIFY)

    response = api_client.get("/jobs")

    assert response.status_code == 200

    jobs = response.json()
    assert len(jobs) == 2
    assert jobs[0]["operation"] == "classify"
    assert jobs[1]["operation"] == "scan"


def test_jobs_get_returns_single_job(api_client, engine):
    with Session(engine) as session:
        service = PipelineJobService(session)
        job = service.create_job(operation=PipelineOperation.SYNC)

    response = api_client.get(f"/jobs/{job.id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == job.id
    assert payload["operation"] == "sync"
    assert payload["status"] == "pending"


def test_jobs_get_missing_returns_404(api_client):
    response = api_client.get("/jobs/999999")

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Job 999999 not found",
    }


def test_jobs_create_persists_job(api_client, engine):
    response = api_client.post(
        "/jobs",
        json={
            "operation": "detect",
            "start": False,
        },
    )

    assert response.status_code == 201

    payload = response.json()
    assert payload["operation"] == "detect"
    assert payload["status"] == "pending"

    with Session(engine) as session:
        job = session.get(PipelineJob, payload["id"])
        assert job is not None
        assert job.operation is PipelineOperation.DETECT


def test_jobs_create_validation_error_for_invalid_operation(api_client):
    response = api_client.post(
        "/jobs",
        json={
            "operation": "not-an-operation",
        },
    )

    assert response.status_code == 422


def test_jobs_create_with_default_start_triggers_dispatch(api_client):
    response = api_client.post(
        "/jobs",
        json={
            "operation": "scan",
        },
    )

    assert response.status_code == 201
    assert api_client.app.state.fake_job_dispatcher.triggers == 1


def test_jobs_cancel_pending_job(api_client, engine):
    with Session(engine) as session:
        service = PipelineJobService(session)
        job = service.create_job(operation=PipelineOperation.SCAN)

    response = api_client.post(f"/jobs/{job.id}/cancel")

    assert response.status_code == 200
    assert response.json()["status"] == "canceled"

    with Session(engine) as session:
        service = PipelineJobService(session)
        persisted = service.repository.get(job.id)
        assert persisted is not None
        assert persisted.status is PipelineJobStatus.CANCELED


def test_jobs_cancel_running_job_conflict(api_client, engine):
    with Session(engine) as session:
        service = PipelineJobService(session)
        job = service.create_job(operation=PipelineOperation.SCAN)
        service.start_job(job)

    response = api_client.post(f"/jobs/{job.id}/cancel")

    assert response.status_code == 409
    assert response.json() == {
        "detail": "Only pending jobs can be canceled",
    }
