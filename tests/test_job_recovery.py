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


def test_running_classification_pass_is_marked_failed_on_recovery(engine):
    from immich_dog_tagger.enums import ClassificationPassStatus
    from immich_dog_tagger.models import ClassificationPass

    with Session(engine) as session:
        job_id = _create_job(session, PipelineJobStatus.RUNNING)

        classification_pass = ClassificationPass(
            status=ClassificationPassStatus.RUNNING,
            classifier_version="v1",
            threshold=0.80,
            job_id=job_id,
        )
        session.add(classification_pass)
        session.commit()
        pass_id = classification_pass.id

        result = recover_interrupted_jobs(session)

    assert result.orphaned_passes == 1

    with Session(engine) as session:
        classification_pass = session.get(ClassificationPass, pass_id)
        assert classification_pass.status is ClassificationPassStatus.FAILED
        assert classification_pass.error_message is not None
        assert classification_pass.completed_at is not None


def test_completed_classification_pass_is_untouched_by_recovery(engine):
    from immich_dog_tagger.enums import ClassificationPassStatus
    from immich_dog_tagger.models import ClassificationPass

    with Session(engine) as session:
        classification_pass = ClassificationPass(
            status=ClassificationPassStatus.COMPLETED,
            classifier_version="v1",
            threshold=0.80,
        )
        session.add(classification_pass)
        session.commit()
        pass_id = classification_pass.id

        result = recover_interrupted_jobs(session)

    assert result.orphaned_passes == 0

    with Session(engine) as session:
        classification_pass = session.get(ClassificationPass, pass_id)
        assert classification_pass.status is ClassificationPassStatus.COMPLETED


def test_active_job_is_not_stuck_while_it_is_making_progress(engine):
    """Issue #134: a running job is healthy, not "stuck", the moment it starts."""

    from immich_dog_tagger.services.job_recovery import find_stuck_jobs

    with Session(engine) as session:
        _create_job(session, PipelineJobStatus.RUNNING)

        assert find_stuck_jobs(session) == []


def test_running_job_is_stuck_once_its_heartbeat_goes_stale(engine):
    from datetime import UTC, datetime, timedelta

    from immich_dog_tagger.services.job_recovery import (
        STUCK_JOB_IDLE_THRESHOLD,
        find_stuck_jobs,
    )

    with Session(engine) as session:
        job_id = _create_job(session, PipelineJobStatus.RUNNING)

        now = datetime.now(UTC).replace(tzinfo=None) + STUCK_JOB_IDLE_THRESHOLD
        assert find_stuck_jobs(session, now=now - timedelta(seconds=5)) == []

        stuck = find_stuck_jobs(session, now=now + timedelta(minutes=30))

        assert [entry.job.id for entry in stuck] == [job_id]
        assert stuck[0].idle_seconds >= STUCK_JOB_IDLE_THRESHOLD.total_seconds()


def test_progress_updates_keep_a_long_running_job_out_of_the_stuck_list(engine):
    from datetime import UTC, datetime, timedelta

    from immich_dog_tagger.models import PipelineJob
    from immich_dog_tagger.services.job_recovery import find_stuck_jobs

    with Session(engine) as session:
        job_id = _create_job(session, PipelineJobStatus.RUNNING)
        job = session.get(PipelineJob, job_id)

        # Backdate the start so the job would be reported without a fresh
        # heartbeat, then report progress the way a running stage does.
        job.started_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=3)
        job.heartbeat_at = job.started_at
        session.commit()

        assert [entry.job.id for entry in find_stuck_jobs(session)] == [job_id]

        PipelineJobService(session).update_progress(job, current=1, total=10)

        assert find_stuck_jobs(session) == []


def test_pending_job_queued_behind_a_running_job_is_never_stuck(engine):
    from datetime import UTC, datetime, timedelta

    from immich_dog_tagger.models import PipelineJob
    from immich_dog_tagger.services.job_recovery import find_stuck_jobs

    with Session(engine) as session:
        running_id = _create_job(session, PipelineJobStatus.RUNNING)
        svc = PipelineJobService(session)
        queued = svc.create_job(operation=PipelineOperation.SYNC)
        queued_id = queued.id
        session.commit()

        # The running job stays healthy; only the queue is slow.
        now = datetime.now(UTC).replace(tzinfo=None) + timedelta(days=1)
        session.get(PipelineJob, running_id).heartbeat_at = now
        session.commit()

        stuck_ids = [entry.job.id for entry in find_stuck_jobs(session, now=now)]

    assert queued_id not in stuck_ids
    assert stuck_ids == []


def test_pending_job_with_nothing_running_is_stuck_after_the_threshold(engine):
    from datetime import UTC, datetime, timedelta

    from immich_dog_tagger.services.job_recovery import find_stuck_jobs

    with Session(engine) as session:
        svc = PipelineJobService(session)
        job = svc.create_job(operation=PipelineOperation.SYNC)
        job_id = job.id
        session.commit()

        assert find_stuck_jobs(session) == []

        now = datetime.now(UTC).replace(tzinfo=None) + timedelta(hours=2)
        stuck = find_stuck_jobs(session, now=now)

    assert [entry.job.id for entry in stuck] == [job_id]


def test_stuck_jobs_are_ordered_by_how_long_they_have_been_idle(engine):
    from datetime import UTC, datetime, timedelta

    from immich_dog_tagger.models import PipelineJob
    from immich_dog_tagger.services.job_recovery import find_stuck_jobs

    with Session(engine) as session:
        first = _create_job(session, PipelineJobStatus.RUNNING)
        second = _create_job(session, PipelineJobStatus.RUNNING)

        now = datetime.now(UTC).replace(tzinfo=None)
        session.get(PipelineJob, first).heartbeat_at = now - timedelta(hours=2)
        session.get(PipelineJob, second).heartbeat_at = now - timedelta(hours=9)
        session.commit()

        stuck = find_stuck_jobs(session, now=now)

    assert [entry.job.id for entry in stuck] == [second, first]
