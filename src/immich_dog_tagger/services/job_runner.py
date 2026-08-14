import logging
import time
from collections.abc import Callable, Mapping
from threading import Lock

from immich_dog_tagger.enums import PipelineJobStatus, PipelineOperation
from immich_dog_tagger.models import PipelineJob
from immich_dog_tagger.services.jobs import PipelineJobRepository, PipelineJobService

logger = logging.getLogger(__name__)


class JobProgressReporter:
    def __init__(
        self,
        service: PipelineJobService,
        job: PipelineJob,
    ):
        self.service = service
        self.job = job

    def set(
        self,
        *,
        current: int,
        total: int | None = None,
        message: str | None = None,
    ) -> PipelineJob:
        self.job = self.service.update_progress(
            self.job,
            current=current,
            total=total,
            message=message,
        )
        return self.job

    def message(
        self,
        value: str,
    ) -> PipelineJob:
        self.job = self.service.update_progress(
            self.job,
            current=self.job.progress_current,
            message=value,
        )
        return self.job


class PipelineJobRunner:
    _execution_lock = Lock()

    def __init__(
        self,
        repository: PipelineJobRepository,
        service: PipelineJobService,
        handlers: Mapping[
            PipelineOperation,
            Callable[[JobProgressReporter], object],
        ],
    ):
        self.repository = repository
        self.service = service
        self.handlers = dict(handlers)

    def run_job(
        self,
        job_id: int,
    ) -> object:
        job = self.repository.get(job_id)

        if job is None:
            raise ValueError(f"Pipeline job not found: {job_id}")

        return self._run(job)

    def run_next_pending(
        self,
    ) -> PipelineJob | None:
        job = self.repository.next_pending()

        if job is None:
            return None

        self._run(job)

        return job

    def _run(
        self,
        job: PipelineJob,
    ) -> object:
        with self._execution_lock:
            if job.status is not PipelineJobStatus.PENDING:
                raise ValueError(
                    f"Pipeline job is not pending and cannot be run: {job.id}"
                )

            if self.repository.has_running_job(exclude_job_id=job.id):
                raise RuntimeError("Another pipeline job is currently running")

            handler = self.handlers.get(job.operation)

            if handler is None:
                raise ValueError(
                    f"No handler registered for pipeline operation: {job.operation.value}"
                )

            job = self.service.start_job(job)
            reporter = JobProgressReporter(self.service, job)

            logger.info("Job %d (%s) started", job.id, job.operation.value)
            started_at = time.monotonic()

            try:
                result = handler(reporter)
                duration = time.monotonic() - started_at

                # Preserve whatever informative final message the handler
                # already set via progress.message()/.set() -- every
                # handler sets one (e.g. "Synchronized 3 identities"), and
                # unconditionally overwriting it with a generic
                # "<operation> completed" here was silently discarding it,
                # leaving no way to tell from the job's own status why a
                # run did (or didn't) do as much as expected. Only fall
                # back to the generic message if the handler never set one.
                self.service.complete_job(
                    job,
                    progress_message=job.progress_message
                    or f"{job.operation.value} completed",
                )

                logger.info(
                    "Job %d (%s) completed in %.2fs",
                    job.id,
                    job.operation.value,
                    duration,
                )
                return result
            except Exception as exc:
                duration = time.monotonic() - started_at
                message = str(exc) or exc.__class__.__name__

                self.service.fail_job(
                    job,
                    error_message=message,
                )

                logger.exception(
                    "Job %d (%s) failed after %.2fs: %s",
                    job.id,
                    job.operation.value,
                    duration,
                    message,
                )
                raise RuntimeError(message) from exc
