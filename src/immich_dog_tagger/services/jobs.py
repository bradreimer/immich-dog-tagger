from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from immich_dog_tagger.enums import PipelineJobStatus, PipelineOperation
from immich_dog_tagger.models import PipelineJob

_TERMINAL_STATUSES = (
    PipelineJobStatus.COMPLETED,
    PipelineJobStatus.FAILED,
    PipelineJobStatus.CANCELED,
)

# Operations whose services commit incrementally (issues #99/#104/#105) and
# so have a checkpoint to roll back to -- the only ones a RUNNING job can be
# cancelled mid-run for (issue #111). EMBED/LEARN/SYNC each do one big
# commit at the end (nothing partial to preserve); RECLASSIFY already
# batches the same way but is a deliberately separate follow-up.
CANCELABLE_WHILE_RUNNING = frozenset(
    {
        PipelineOperation.SCAN,
        PipelineOperation.DETECT,
        PipelineOperation.CLASSIFY,
        PipelineOperation.FULL_PIPELINE,
    }
)


class PipelineJobRepository:
    def __init__(
        self,
        session: Session,
    ):
        self.session = session

    def create(
        self,
        *,
        operation: PipelineOperation,
        progress_total: int | None = None,
        progress_message: str | None = None,
    ) -> PipelineJob:
        job = PipelineJob(
            operation=operation,
            progress_total=progress_total,
            progress_message=progress_message,
        )

        self.session.add(job)
        self.session.flush()

        return job

    def get(
        self,
        job_id: int,
    ) -> PipelineJob | None:
        return self.session.get(PipelineJob, job_id)

    def list_recent(
        self,
        *,
        limit: int = 100,
    ) -> list[PipelineJob]:
        return self.session.scalars(
            select(PipelineJob)
            .where(PipelineJob.visible.is_(True))
            .order_by(PipelineJob.id.desc())
            .limit(limit)
        ).all()

    def next_pending(
        self,
    ) -> PipelineJob | None:
        return self.session.scalar(
            select(PipelineJob)
            .where(PipelineJob.status == PipelineJobStatus.PENDING)
            .order_by(PipelineJob.id.asc())
            .limit(1)
        )

    def has_running_job(
        self,
        *,
        exclude_job_id: int | None = None,
    ) -> bool:
        query = select(PipelineJob).where(
            PipelineJob.status == PipelineJobStatus.RUNNING,
        )

        if exclude_job_id is not None:
            query = query.where(PipelineJob.id != exclude_job_id)

        return self.session.scalar(query.limit(1)) is not None

    def status_counts(self) -> dict[PipelineJobStatus, int]:
        rows = self.session.execute(
            select(PipelineJob.status, func.count(PipelineJob.id)).group_by(
                PipelineJob.status
            )
        ).all()

        return {status: count for status, count in rows}

    def recent_failures(self, *, limit: int = 5) -> list[PipelineJob]:
        return self.session.scalars(
            select(PipelineJob)
            .where(PipelineJob.status == PipelineJobStatus.FAILED)
            .order_by(PipelineJob.completed_at.desc())
            .limit(limit)
        ).all()

    def hide_finished_jobs(self) -> int:
        """
        "Clear list": hides every currently-visible finished job (never a
        pending/running one) from list_recent()'s default result set. Rows
        are kept, not deleted -- state.db stays the source of truth for job
        history (ADR-001); this only changes what's displayed by default.
        """
        result = self.session.execute(
            update(PipelineJob)
            .where(PipelineJob.status.in_(_TERMINAL_STATUSES))
            .where(PipelineJob.visible.is_(True))
            .values(visible=False)
        )

        return result.rowcount


class PipelineJobService:
    def __init__(
        self,
        session: Session,
        repository: PipelineJobRepository | None = None,
    ):
        self.session = session
        self.repository = repository or PipelineJobRepository(session)

    def create_job(
        self,
        *,
        operation: PipelineOperation,
        progress_total: int | None = None,
        progress_message: str | None = None,
    ) -> PipelineJob:
        job = self.repository.create(
            operation=operation,
            progress_total=progress_total,
            progress_message=progress_message,
        )
        self.session.commit()
        self.session.refresh(job)
        return job

    def start_job(
        self,
        job: PipelineJob,
    ) -> PipelineJob:
        job.transition_to(PipelineJobStatus.RUNNING)
        self.session.commit()
        self.session.refresh(job)
        return job

    def complete_job(
        self,
        job: PipelineJob,
        *,
        progress_message: str | None = None,
    ) -> PipelineJob:
        if job.progress_total is not None:
            job.progress_current = job.progress_total

        if progress_message is not None:
            job.progress_message = progress_message

        job.transition_to(PipelineJobStatus.COMPLETED)

        self.session.commit()
        self.session.refresh(job)
        return job

    def fail_job(
        self,
        job: PipelineJob,
        *,
        error_message: str,
    ) -> PipelineJob:
        job.error_message = error_message
        job.transition_to(PipelineJobStatus.FAILED)

        self.session.commit()
        self.session.refresh(job)
        return job

    def cancel_job(
        self,
        job: PipelineJob,
    ) -> PipelineJob:
        if job.status is PipelineJobStatus.PENDING:
            job.transition_to(PipelineJobStatus.CANCELED)
            self.session.commit()
            self.session.refresh(job)
            return job

        if (
            job.status is PipelineJobStatus.RUNNING
            and job.operation in CANCELABLE_WHILE_RUNNING
        ):
            # Atomic UPDATE...WHERE, not a read-then-write on the already
            # loaded `job` -- the job could finish (complete_job) between
            # this request being received and committed, and a plain
            # attribute-mutate-then-commit would silently set
            # cancel_requested on an already-terminal row.
            result = self.session.execute(
                update(PipelineJob)
                .where(
                    PipelineJob.id == job.id,
                    PipelineJob.status == PipelineJobStatus.RUNNING,
                )
                .values(cancel_requested=True)
            )
            self.session.commit()

            if result.rowcount == 0:
                raise ValueError("Job is not running and cannot be canceled")

            self.session.refresh(job)
            return job

        if job.status is PipelineJobStatus.RUNNING:
            raise ValueError(
                f"{job.operation.value} jobs cannot be canceled once running"
            )

        raise ValueError("Job is not pending or running and cannot be canceled")

    def finish_canceled_job(
        self,
        job: PipelineJob,
        *,
        progress_message: str | None = None,
    ) -> PipelineJob:
        """
        Finalizes a RUNNING job that honored a cancel_requested flag
        (issue #111). Unlike complete_job(), this never forces
        progress_current up to progress_total -- the progress fields
        already reflect the last completed batch, and rounding them up to
        100% would misrepresent a run that stopped partway through.
        """
        if progress_message is not None:
            job.progress_message = progress_message

        job.cancel_requested = False
        job.transition_to(PipelineJobStatus.CANCELED)

        self.session.commit()
        self.session.refresh(job)
        return job

    def is_cancel_requested(self, job_id: int) -> bool:
        """
        A fresh, single-column read straight from the DB -- selecting an
        individual column (rather than the full PipelineJob entity) always
        issues real SQL rather than returning a possibly-stale value from
        the session's identity map, which matters here since the flag is
        set by a different session (issue #111).
        """
        return bool(
            self.session.execute(
                select(PipelineJob.cancel_requested).where(PipelineJob.id == job_id)
            ).scalar_one()
        )

    def status_counts(self) -> dict[PipelineJobStatus, int]:
        return self.repository.status_counts()

    def recent_failures(self, *, limit: int = 5) -> list[PipelineJob]:
        return self.repository.recent_failures(limit=limit)

    def clear_history(self) -> int:
        cleared = self.repository.hide_finished_jobs()
        self.session.commit()
        return cleared

    def update_progress(
        self,
        job: PipelineJob,
        *,
        current: int,
        total: int | None = None,
        message: str | None = None,
    ) -> PipelineJob:
        if current < 0:
            raise ValueError("Progress current value cannot be negative")

        if total is not None:
            if total < 0:
                raise ValueError("Progress total value cannot be negative")

            if current > total:
                raise ValueError("Progress current value cannot exceed total")

            job.progress_total = total

        if job.progress_total is not None and current > job.progress_total:
            raise ValueError("Progress current value cannot exceed total")

        job.progress_current = current

        if message is not None:
            job.progress_message = message

        # Every progress report is also proof the job is still alive
        # (issue #134). This is the only safe place to stamp it: the
        # heartbeat has to ride along with a commit the job was already
        # making at a checkpoint of its own, never an extra write squeezed
        # into the middle of a batch a service may still roll back.
        job.heartbeat_at = datetime.now(UTC).replace(tzinfo=None)

        self.session.commit()
        self.session.refresh(job)
        return job
