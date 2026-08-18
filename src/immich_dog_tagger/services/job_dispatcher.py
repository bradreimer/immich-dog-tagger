import logging
from collections.abc import Callable
from threading import Lock, Thread

from sqlalchemy.orm import Session

from immich_dog_tagger.services.job_runner import PipelineJobRunner

logger = logging.getLogger(__name__)


class PipelineJobDispatcher:
    def __init__(
        self,
        engine_factory: Callable[[], object],
        runner_factory: Callable[[Session], PipelineJobRunner],
    ):
        self.engine_factory = engine_factory
        self.runner_factory = runner_factory
        self._lock = Lock()
        self._running = False
        self._needs_run = False

    def trigger(self) -> None:
        with self._lock:
            self._needs_run = True

            if self._running:
                return

            self._running = True

        thread = Thread(
            target=self._drain,
            daemon=True,
        )
        thread.start()

    def _drain(self) -> None:
        while True:
            with self._lock:
                should_run = self._needs_run
                self._needs_run = False

            if not should_run:
                with self._lock:
                    self._running = False
                return

            while True:
                engine = self.engine_factory()

                with Session(engine) as session:
                    runner = self.runner_factory(session)

                    job = runner.repository.next_pending()
                    if job is None:
                        break

                    try:
                        runner.run_job(job.id)
                    except (RuntimeError, ValueError) as exc:
                        # Failed jobs are persisted (and logged with their
                        # traceback) by the runner itself; the dispatcher only
                        # needs to keep draining the queue.
                        logger.debug("Job %d raised while dispatching: %s", job.id, exc)
                        continue
