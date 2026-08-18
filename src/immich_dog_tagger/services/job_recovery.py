"""Recover interrupted PipelineJobs after process restart."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from immich_dog_tagger.enums import ClassificationPassStatus, PipelineJobStatus
from immich_dog_tagger.models import ClassificationPass, PipelineJob

logger = logging.getLogger(__name__)

_INTERRUPTED_MSG = (
    "Interrupted: process stopped while this job was active. Retry from Overview."
)
_ABANDONED_MSG = (
    "Abandoned: process stopped before this job could start. Retry from Overview."
)

# How long a job may go without any sign of life before Overview flags it
# (issue #134). Deliberately generous: a job's heartbeat is refreshed by its
# own progress reports, and the coarsest of those sit at stage boundaries
# (a full detect batch of 1000 assets is a single stage), so anything
# tighter would flag healthy long-running work -- exactly the false alarm
# this threshold exists to remove. The failure it does catch (a job whose
# process died while its row still says RUNNING) stays stale forever, so
# noticing it an hour late costs nothing.
STUCK_JOB_IDLE_THRESHOLD = timedelta(hours=1)


@dataclass
class RecoveryResult:
    failed: int  # jobs that were RUNNING → FAILED
    canceled: int  # jobs that were PENDING → CANCELED
    orphaned_passes: int = 0  # classification passes reconciled to FAILED

    @property
    def total(self) -> int:
        return self.failed + self.canceled


def recover_interrupted_jobs(session: Session) -> RecoveryResult:
    """Mark jobs left in active states as FAILED/CANCELED after a restart."""
    running = session.scalars(
        select(PipelineJob).where(PipelineJob.status == PipelineJobStatus.RUNNING)
    ).all()
    pending = session.scalars(
        select(PipelineJob).where(PipelineJob.status == PipelineJobStatus.PENDING)
    ).all()

    for job in running:
        job.error_message = _INTERRUPTED_MSG
        job.transition_to(PipelineJobStatus.FAILED)

    for job in pending:
        job.error_message = _ABANDONED_MSG
        job.transition_to(PipelineJobStatus.CANCELED)

    orphaned_passes = _recover_orphaned_classification_passes(session)

    session.commit()

    if running or pending:
        logger.warning(
            "Startup recovery: %d interrupted job(s) marked FAILED, %d abandoned job(s) "
            "marked CANCELED, %d classification pass(es) reconciled",
            len(running),
            len(pending),
            orphaned_passes,
        )

    return RecoveryResult(
        failed=len(running),
        canceled=len(pending),
        orphaned_passes=orphaned_passes,
    )


def _recover_orphaned_classification_passes(session: Session) -> int:
    """
    A ClassificationPass is only ever driven synchronously within a single
    job execution -- nothing resumes a RUNNING pass across a process
    restart. So a pass still marked RUNNING at startup is, by definition,
    one whose owning process died mid-run and never reached the exception
    handler that would otherwise have marked it FAILED. Without this, the
    pass would sit at RUNNING forever and be reported as an active
    Reclassify to operators even though nothing is running.
    """
    stuck_passes = session.scalars(
        select(ClassificationPass).where(
            ClassificationPass.status == ClassificationPassStatus.RUNNING,
        )
    ).all()

    for classification_pass in stuck_passes:
        classification_pass.status = ClassificationPassStatus.FAILED
        classification_pass.error_message = _INTERRUPTED_MSG
        classification_pass.completed_at = datetime.now(UTC).replace(tzinfo=None)

    return len(stuck_passes)


@dataclass(frozen=True)
class StuckJob:
    """A job that is nominally active but has shown no sign of life."""

    job: PipelineJob
    idle_seconds: int


def find_stuck_jobs(
    session: Session,
    *,
    now: datetime | None = None,
    threshold: timedelta = STUCK_JOB_IDLE_THRESHOLD,
) -> list[StuckJob]:
    """
    Active jobs that have stopped making progress, worst offender first.

    A RUNNING job is normal, and so is a PENDING job queued behind one --
    reporting either as "stuck" merely because of its status (as
    /diagnostics used to) makes the warning fire on every job the moment it
    starts. What is abnormal is an active job whose last activity is older
    than `threshold`:

    * RUNNING with a stale heartbeat -- its process died between the row
      being written and the exception handler that would have failed it, or
      its thread is wedged.
    * PENDING while *nothing* is running -- there is no job ahead of it in
      the queue, so something should have picked it up long ago. A PENDING
      job with a RUNNING job ahead of it is just waiting its turn and is
      never reported, however long the queue takes.
    """

    now = now or datetime.now(UTC).replace(tzinfo=None)

    running = session.scalars(
        select(PipelineJob).where(PipelineJob.status == PipelineJobStatus.RUNNING)
    ).all()

    candidates = list(running)

    if not running:
        candidates.extend(
            session.scalars(
                select(PipelineJob).where(
                    PipelineJob.status == PipelineJobStatus.PENDING
                )
            ).all()
        )

    stuck = [
        StuckJob(job=job, idle_seconds=int(idle.total_seconds()))
        for job, idle in ((job, now - job.last_activity_at) for job in candidates)
        if idle >= threshold
    ]

    return sorted(stuck, key=lambda entry: entry.idle_seconds, reverse=True)
