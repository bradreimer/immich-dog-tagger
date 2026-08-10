"""Recover interrupted PipelineJobs after process restart."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from immich_dog_tagger.enums import PipelineJobStatus
from immich_dog_tagger.models import PipelineJob

logger = logging.getLogger(__name__)

_INTERRUPTED_MSG = "Interrupted: process stopped while this job was active. Retry from Mission Control."
_ABANDONED_MSG = "Abandoned: process stopped before this job could start. Retry from Mission Control."


@dataclass
class RecoveryResult:
    failed: int  # jobs that were RUNNING → FAILED
    canceled: int  # jobs that were PENDING → CANCELED

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

    session.commit()

    if running or pending:
        logger.warning(
            "Startup recovery: %d interrupted job(s) marked FAILED, %d abandoned job(s) marked CANCELED",
            len(running),
            len(pending),
        )

    return RecoveryResult(failed=len(running), canceled=len(pending))
