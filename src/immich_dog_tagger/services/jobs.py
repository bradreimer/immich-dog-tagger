from sqlalchemy import select
from sqlalchemy.orm import Session

from immich_dog_tagger.enums import PipelineJobStatus, PipelineOperation
from immich_dog_tagger.models import PipelineJob


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
            select(PipelineJob).order_by(PipelineJob.id.desc()).limit(limit)
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
        if job.status is not PipelineJobStatus.PENDING:
            raise ValueError("Only pending jobs can be canceled")

        job.transition_to(PipelineJobStatus.CANCELED)

        self.session.commit()
        self.session.refresh(job)
        return job

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

        self.session.commit()
        self.session.refresh(job)
        return job
