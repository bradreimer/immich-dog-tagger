"""Tests for interrupted job recovery."""

from __future__ import annotations

from sqlalchemy.orm import Session

from immich_dog_tagger.enums import PipelineJobStatus, PipelineOperation
from immich_dog_tagger.services.job_recovery import recover_interrupted_jobs
from immich_dog_tagger.services.jobs import PipelineJobService


def _create_job(session: Session, status: PipelineJobStatus) -> int:
    svc = PipelineJobService(session)
    job = svc.create_job(operation=PipelineOperation.FULL_PIPELINE)
    if status == PipelineJobStatus.RUNNING:
        job.transition_to(PipelineJobStatus.RUNNING)
        session.commit()
    elif status == PipelineJobStatus.CANCELED:
        job.transition_to(PipelineJobStatus.CANCELED)
        session.commit()
    return job.id


def test_running_jobs_are_marked_failed_on_recovery(engine):
    from immich_dog_tagger.models import PipelineJob

    with Session(engine) as session:
        job_id = _create_job(session, PipelineJobStatus.RUNNING)
        result = recover_interrupted_jobs(session)

    assert result.failed == 1
    assert result.canceled == 0

    with Session(engine) as session:
        job = session.get(PipelineJob, job_id)
        assert job.status is PipelineJobStatus.FAILED
        assert job.error_message is not None


def test_pending_jobs_are_canceled_on_recovery(engine):
    with Session(engine) as session:
        svc = PipelineJobService(session)
        job = svc.create_job(operation=PipelineOperation.FULL_PIPELINE)
        job_id = job.id
        session.commit()
        result = recover_interrupted_jobs(session)

    with Session(engine) as session:
        from immich_dog_tagger.models import PipelineJob

        job = session.get(PipelineJob, job_id)
        assert job.status is PipelineJobStatus.CANCELED
    assert result.canceled == 1
    assert result.failed == 0


def test_completed_jobs_are_untouched_by_recovery(engine):
    with Session(engine) as session:
        svc = PipelineJobService(session)
        job = svc.create_job(operation=PipelineOperation.FULL_PIPELINE)
        job_id = job.id
        job.transition_to(PipelineJobStatus.RUNNING)
        job.transition_to(PipelineJobStatus.COMPLETED)
        session.commit()
        result = recover_interrupted_jobs(session)

    assert result.total == 0
    with Session(engine) as session:
        from immich_dog_tagger.models import PipelineJob

        job = session.get(PipelineJob, job_id)
        assert job.status is PipelineJobStatus.COMPLETED


def test_recovery_result_total():
    from immich_dog_tagger.services.job_recovery import RecoveryResult

    r = RecoveryResult(failed=2, canceled=3)
    assert r.total == 5
