import pytest
from sqlalchemy.orm import Session

from immich_dog_tagger.enums import PipelineJobStatus, PipelineOperation
from immich_dog_tagger.services.job_runner import PipelineJobRunner
from immich_dog_tagger.services.jobs import PipelineJobRepository, PipelineJobService


def build_runner(
    session: Session,
    handlers,
) -> PipelineJobRunner:
    repository = PipelineJobRepository(session)
    service = PipelineJobService(session, repository=repository)
    return PipelineJobRunner(
        repository=repository,
        service=service,
        handlers=handlers,
    )


def test_runner_executes_queued_job_and_marks_completed(engine):
    with Session(engine) as session:
        service = PipelineJobService(session)
        job = service.create_job(operation=PipelineOperation.SCAN)

        events = []

        def scan_handler(progress):
            progress.set(current=0, total=2, message="Scanning")
            progress.set(current=1, message="Halfway")
            progress.set(current=2, message="Done")
            events.append("scan")
            return {"scanned": 2}

        runner = build_runner(
            session,
            {
                PipelineOperation.SCAN: scan_handler,
            },
        )

        result = runner.run_job(job.id)
        session.refresh(job)

        assert result == {"scanned": 2}
        assert events == ["scan"]
        assert job.status is PipelineJobStatus.COMPLETED
        assert job.started_at is not None
        assert job.completed_at is not None
        assert job.progress_current == 2
        assert job.progress_total == 2
        # The handler's own last message survives completion -- it must
        # not be silently replaced by a generic "scan completed".
        assert job.progress_message == "Done"


def test_runner_falls_back_to_generic_message_when_handler_sets_none(engine):
    """A handler that never calls progress.message()/.set() with a message
    still needs some completion message -- the generic fallback only
    applies in that case, not whenever a handler happens to finish."""
    with Session(engine) as session:
        service = PipelineJobService(session)
        job = service.create_job(operation=PipelineOperation.LEARN)

        runner = build_runner(
            session,
            {
                PipelineOperation.LEARN: lambda progress: {"imported": 0},
            },
        )

        runner.run_job(job.id)
        session.refresh(job)

        assert job.progress_message == "learn completed"


def test_runner_marks_failed_and_preserves_job_on_exception(engine):
    with Session(engine) as session:
        service = PipelineJobService(session)
        job = service.create_job(operation=PipelineOperation.DETECT)

        def detect_handler(progress):
            progress.message("Detecting")
            raise RuntimeError("detector error")

        runner = build_runner(
            session,
            {
                PipelineOperation.DETECT: detect_handler,
            },
        )

        with pytest.raises(RuntimeError, match="detector error"):
            runner.run_job(job.id)

        session.refresh(job)

        assert job.status is PipelineJobStatus.FAILED
        assert job.error_message == "detector error"
        assert job.started_at is not None
        assert job.completed_at is not None


def test_runner_logs_traceback_on_failure(engine, caplog):
    # Regression test for issue #88: the failure log previously carried
    # only the bare exception message, with no traceback -- making
    # asset-specific failures slow to root-cause from logs alone.
    with Session(engine) as session:
        service = PipelineJobService(session)
        job = service.create_job(operation=PipelineOperation.DETECT)

        def detect_handler(progress):
            raise RuntimeError("detector error")

        runner = build_runner(
            session,
            {
                PipelineOperation.DETECT: detect_handler,
            },
        )

        with caplog.at_level("ERROR"), pytest.raises(RuntimeError):
            runner.run_job(job.id)

        failure_records = [
            record for record in caplog.records if record.levelname == "ERROR"
        ]

        assert len(failure_records) == 1
        assert failure_records[0].exc_info is not None


def test_runner_rejects_execution_when_another_job_is_running(engine):
    with Session(engine) as session:
        repository = PipelineJobRepository(session)
        service = PipelineJobService(session, repository=repository)

        running_job = service.create_job(operation=PipelineOperation.SYNC)
        service.start_job(running_job)

        pending_job = service.create_job(operation=PipelineOperation.CLASSIFY)

        runner = PipelineJobRunner(
            repository=repository,
            service=service,
            handlers={
                PipelineOperation.CLASSIFY: lambda progress: None,
            },
        )

        with pytest.raises(RuntimeError, match="currently running"):
            runner.run_job(pending_job.id)

        session.refresh(pending_job)
        assert pending_job.status is PipelineJobStatus.PENDING


def test_runner_can_process_next_pending_job_in_queue_order(engine):
    with Session(engine) as session:
        service = PipelineJobService(session)

        first = service.create_job(operation=PipelineOperation.SCAN)
        second = service.create_job(operation=PipelineOperation.SCAN)

        called = []

        runner = build_runner(
            session,
            {
                PipelineOperation.SCAN: lambda progress: called.append("scan"),
            },
        )

        processed = runner.run_next_pending()

        assert processed is not None
        assert processed.id == first.id

        session.refresh(first)
        session.refresh(second)

        assert called == ["scan"]
        assert first.status is PipelineJobStatus.COMPLETED
        assert second.status is PipelineJobStatus.PENDING


def test_runner_uses_injected_handler_mapping(engine):
    with Session(engine) as session:
        service = PipelineJobService(session)
        job = service.create_job(operation=PipelineOperation.LEARN)

        marker = {"called": False}

        def learn_handler(progress):
            marker["called"] = True

        runner = build_runner(
            session,
            {
                PipelineOperation.LEARN: learn_handler,
            },
        )

        runner.run_job(job.id)

        assert marker["called"] is True


def test_runner_requires_registered_operation_handler(engine):
    with Session(engine) as session:
        service = PipelineJobService(session)
        job = service.create_job(operation=PipelineOperation.EMBED)

        runner = build_runner(session, {})

        with pytest.raises(ValueError, match="No handler registered"):
            runner.run_job(job.id)


def test_runner_rejects_non_pending_job(engine):
    with Session(engine) as session:
        service = PipelineJobService(session)
        job = service.create_job(operation=PipelineOperation.SCAN)
        service.start_job(job)

        runner = build_runner(
            session,
            {
                PipelineOperation.SCAN: lambda progress: None,
            },
        )

        with pytest.raises(ValueError, match="is not pending"):
            runner.run_job(job.id)
