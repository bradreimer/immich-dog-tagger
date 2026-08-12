"""Recover interrupted PipelineJobs after process restart."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime

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
