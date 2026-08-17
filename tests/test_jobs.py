from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from immich_dog_tagger.database import create_database
from immich_dog_tagger.enums import PipelineJobStatus, PipelineOperation
from immich_dog_tagger.models import PipelineJob
from immich_dog_tagger.services.jobs import PipelineJobRepository, PipelineJobService

CANCELABLE_OPERATION = PipelineOperation.SCAN
NON_CANCELABLE_OPERATION = PipelineOperation.SYNC


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


def test_pipeline_job_running_can_transition_to_canceled(engine):
    # Issue #111: a RUNNING job's own execution loop transitions itself to
    # CANCELED once it honors a cancel_requested flag -- this must be a
    # legal transition alongside the existing COMPLETED/FAILED targets.
    with Session(engine) as session:
        job = PipelineJob(operation=PipelineOperation.SCAN)
        session.add(job)
        session.flush()

        assert job.can_transition_to(PipelineJobStatus.CANCELED)

        job.transition_to(PipelineJobStatus.RUNNING)
        job.transition_to(PipelineJobStatus.CANCELED)

        session.commit()

        assert job.status is PipelineJobStatus.CANCELED
        assert job.completed_at is not None


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


def test_clear_history_hides_only_finished_jobs(engine):
    """DT-1116 / issue #12: "Clear list" must actually persist server-side
    -- a completed job hidden by clear_history() must not come back from
    list_recent(), and pending/running jobs must never be hidden by it."""
    with Session(engine) as session:
        service = PipelineJobService(session)

        completed = service.create_job(operation=PipelineOperation.SCAN)
        service.start_job(completed)
        service.complete_job(completed)

        failed = service.create_job(operation=PipelineOperation.DETECT)
        service.start_job(failed)
        service.fail_job(failed, error_message="boom")

        pending = service.create_job(operation=PipelineOperation.CLASSIFY)

        running = service.create_job(operation=PipelineOperation.EMBED)
        service.start_job(running)

        cleared = service.clear_history()

        assert cleared == 2

        visible_ids = {job.id for job in service.repository.list_recent()}

        assert completed.id not in visible_ids
        assert failed.id not in visible_ids
        assert pending.id in visible_ids
        assert running.id in visible_ids


def test_clear_history_is_idempotent(engine):
    with Session(engine) as session:
        service = PipelineJobService(session)

        job = service.create_job(operation=PipelineOperation.SCAN)
        service.start_job(job)
        service.complete_job(job)

        first = service.clear_history()
        second = service.clear_history()

        assert first == 1
        assert second == 0


def test_cancel_job_pending_transitions_immediately(engine):
    with Session(engine) as session:
        service = PipelineJobService(session)
        job = service.create_job(operation=CANCELABLE_OPERATION)

        service.cancel_job(job)

        assert job.status is PipelineJobStatus.CANCELED
        assert job.cancel_requested is False


def test_cancel_job_running_cancelable_sets_flag_without_changing_status(engine):
    with Session(engine) as session:
        service = PipelineJobService(session)
        job = service.create_job(operation=CANCELABLE_OPERATION)
        service.start_job(job)

        result = service.cancel_job(job)

        assert result.status is PipelineJobStatus.RUNNING
        assert result.cancel_requested is True

        # Calling again while still pending is a harmless no-op, not an
        # error -- a user double-clicking Cancel shouldn't see a failure.
        again = service.cancel_job(job)
        assert again.cancel_requested is True


def test_cancel_job_running_non_cancelable_operation_rejected(engine):
    with Session(engine) as session:
        service = PipelineJobService(session)
        job = service.create_job(operation=NON_CANCELABLE_OPERATION)
        service.start_job(job)

        with pytest.raises(ValueError, match="cannot be canceled once running"):
            service.cancel_job(job)

        assert job.cancel_requested is False


def test_cancel_job_terminal_job_rejected(engine):
    with Session(engine) as session:
        service = PipelineJobService(session)
        job = service.create_job(operation=CANCELABLE_OPERATION)
        service.start_job(job)
        service.complete_job(job)

        with pytest.raises(ValueError, match="not pending or running"):
            service.cancel_job(job)


def test_cancel_job_running_race_against_concurrent_completion(engine):
    """Issue #111: cancel_job() must not silently set cancel_requested on a
    job that finished between being loaded and this call committing -- the
    atomic UPDATE...WHERE status='RUNNING' guard, not a read-then-write on
    the already-loaded ORM object, is what catches this. Uses two
    independent sessions (one for the "job finishing" side, one for the
    "cancel request" side, each with its own stale-vs-fresh view) to
    reproduce the actual cross-session race rather than a single session's
    in-memory attribute mutation, which autoflush would just reconcile
    away."""
    with Session(engine) as setup_session:
        setup_service = PipelineJobService(setup_session)
        job = setup_service.create_job(operation=CANCELABLE_OPERATION)
        setup_service.start_job(job)
        job_id = job.id

    with (
        Session(engine) as cancel_session,
        Session(engine) as completion_session,
    ):
        cancel_service = PipelineJobService(cancel_session)
        completion_service = PipelineJobService(completion_session)

        # The cancel request's session loads the job while it's still
        # RUNNING...
        stale_job = cancel_service.repository.get(job_id)
        assert stale_job.status is PipelineJobStatus.RUNNING

        # ...then, before cancel_job() gets to write, the job finishes via
        # a completely separate session/connection.
        live_job = completion_service.repository.get(job_id)
        completion_service.complete_job(live_job)

        with pytest.raises(ValueError, match="not running"):
            cancel_service.cancel_job(stale_job)

    with Session(engine) as session:
        persisted = PipelineJobRepository(session).get(job_id)
        assert persisted.status is PipelineJobStatus.COMPLETED
        assert persisted.cancel_requested is False


def test_finish_canceled_job_transitions_and_clears_flag(engine):
    with Session(engine) as session:
        service = PipelineJobService(session)
        job = service.create_job(
            operation=CANCELABLE_OPERATION,
            progress_total=100,
        )
        service.start_job(job)
        service.update_progress(job, current=40, message="Batch 4 complete")
        service.cancel_job(job)

        result = service.finish_canceled_job(job, progress_message="Canceled")

        assert result.status is PipelineJobStatus.CANCELED
        assert result.cancel_requested is False
        # Unlike complete_job(), progress_current is left reflecting the
        # last completed batch rather than forced up to progress_total.
        assert result.progress_current == 40
        assert result.progress_total == 100
        assert result.progress_message == "Canceled"


def test_is_cancel_requested_reflects_a_fresh_db_read(engine):
    with Session(engine) as session:
        service = PipelineJobService(session)
        job = service.create_job(operation=CANCELABLE_OPERATION)
        service.start_job(job)

        assert service.is_cancel_requested(job.id) is False

    # A different session sets the flag, matching how the API's cancel
    # request and the running job's own execution session are separate.
    with Session(engine) as other_session:
        other_service = PipelineJobService(other_session)
        other_service.cancel_job(other_service.repository.get(job.id))

    with Session(engine) as session:
        service = PipelineJobService(session)
        assert service.is_cancel_requested(job.id) is True
