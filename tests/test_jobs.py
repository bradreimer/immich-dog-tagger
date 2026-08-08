from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from immich_dog_tagger.database import create_database
from immich_dog_tagger.enums import PipelineJobStatus, PipelineOperation
from immich_dog_tagger.models import PipelineJob
from immich_dog_tagger.services.jobs import PipelineJobRepository, PipelineJobService


def test_pipeline_operation_enum_values():
    assert PipelineOperation.SCAN == "scan"
    assert PipelineOperation.DETECT == "detect"
    assert PipelineOperation.EMBED == "embed"
    assert PipelineOperation.CLASSIFY == "classify"
    assert PipelineOperation.LEARN == "learn"
    assert PipelineOperation.SYNC == "sync"
    assert PipelineOperation.FULL_PIPELINE == "full_pipeline"


def test_pipeline_job_can_persist_and_be_retrieved(engine):
    with Session(engine) as session:
        repository = PipelineJobRepository(session)
        job = repository.create(
            operation=PipelineOperation.SCAN,
            progress_total=10,
            progress_message="Queued",
        )
        session.commit()
        job_id = job.id

    with Session(engine) as session:
        repository = PipelineJobRepository(session)
        persisted = repository.get(job_id)

        assert persisted is not None
        assert persisted.id == job_id
        assert persisted.operation is PipelineOperation.SCAN
        assert persisted.status is PipelineJobStatus.PENDING
        assert persisted.progress_total == 10
        assert persisted.progress_current == 0
        assert persisted.progress_message == "Queued"
        assert persisted.created_at is not None
        assert persisted.started_at is None
        assert persisted.completed_at is None


def test_pipeline_job_valid_lifecycle_transitions(engine):
    with Session(engine) as session:
        job = PipelineJob(operation=PipelineOperation.FULL_PIPELINE)
        session.add(job)
        session.flush()

        start_time = datetime.now(UTC).replace(tzinfo=None)
        end_time = start_time + timedelta(seconds=1)

        job.transition_to(PipelineJobStatus.RUNNING, now=start_time)
        job.transition_to(PipelineJobStatus.COMPLETED, now=end_time)

        session.commit()

        assert job.status is PipelineJobStatus.COMPLETED
        assert job.started_at == start_time
        assert job.completed_at == end_time


def test_pipeline_job_invalid_lifecycle_transitions_rejected(engine):
    with Session(engine) as session:
        pending_job = PipelineJob(operation=PipelineOperation.DETECT)
        session.add(pending_job)
        session.flush()

        with pytest.raises(ValueError, match="Invalid pipeline job transition"):
            pending_job.transition_to(PipelineJobStatus.COMPLETED)

        pending_job.transition_to(PipelineJobStatus.RUNNING)
        pending_job.transition_to(PipelineJobStatus.FAILED)

        with pytest.raises(ValueError, match="Invalid pipeline job transition"):
            pending_job.transition_to(PipelineJobStatus.RUNNING)


def test_pipeline_job_state_survives_database_reopen(tmp_path: Path):
    engine = create_database(tmp_path)

    with Session(engine) as session:
        service = PipelineJobService(session)
        job = service.create_job(operation=PipelineOperation.SYNC)
        job_id = job.id

    reopened_engine = create_database(tmp_path)

    with Session(reopened_engine) as session:
        repository = PipelineJobRepository(session)
        persisted = repository.get(job_id)

        assert persisted is not None
        assert persisted.status is PipelineJobStatus.PENDING
        assert persisted.operation is PipelineOperation.SYNC


def test_pipeline_job_service_progress_and_completion(engine):
    with Session(engine) as session:
        service = PipelineJobService(session)

        job = service.create_job(
            operation=PipelineOperation.EMBED,
            progress_total=5,
            progress_message="Queued",
        )

        service.start_job(job)
        service.update_progress(
            job,
            current=3,
            message="Embedding in progress",
        )
        service.complete_job(job, progress_message="Finished")

        assert job.status is PipelineJobStatus.COMPLETED
        assert job.progress_current == 5
        assert job.progress_total == 5
        assert job.progress_message == "Finished"
        assert job.started_at is not None
        assert job.completed_at is not None


def test_pipeline_job_service_rejects_invalid_progress(engine):
    with Session(engine) as session:
        service = PipelineJobService(session)

        job = service.create_job(
            operation=PipelineOperation.CLASSIFY,
            progress_total=4,
        )

        with pytest.raises(ValueError, match="cannot exceed total"):
            service.update_progress(
                job,
                current=5,
            )
