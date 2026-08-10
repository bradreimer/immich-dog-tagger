"""Background scheduler loop — runs in a dedicated thread."""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from immich_dog_tagger.config import Config
from immich_dog_tagger.services.job_execution import create_pipeline_job_runner
from immich_dog_tagger.services.scheduler import SchedulerService

logger = logging.getLogger(__name__)

TICK_INTERVAL_SECONDS = 60


@dataclass
class SchedulerHealth:
    started_at: datetime | None = None
    last_tick_at: datetime | None = None
    last_error_at: datetime | None = None
    last_error: str | None = None
    ticks: int = 0
    errors: int = 0

    @property
    def healthy(self) -> bool:
        if self.last_error_at is None:
            return True
        if self.last_tick_at is None:
            return False
        return self.last_tick_at >= self.last_error_at

    def as_dict(self) -> dict:
        return {
            "healthy": self.healthy,
            "ticks": self.ticks,
            "errors": self.errors,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "last_tick_at": self.last_tick_at.isoformat()
            if self.last_tick_at
            else None,
            "last_error_at": self.last_error_at.isoformat()
            if self.last_error_at
            else None,
            "last_error": self.last_error,
        }


def _tick(engine: Engine, config: Config, health: SchedulerHealth) -> None:
    with Session(engine) as session:
        runner = create_pipeline_job_runner(session, config)
        scheduler = SchedulerService(session, runner=runner)
        dispatched = scheduler.dispatch_due_schedules()
        if dispatched:
            logger.info("Scheduler dispatched %d job(s) this tick", len(dispatched))
    health.last_tick_at = datetime.now(UTC)
    health.ticks += 1


def run_scheduler(
    engine: Engine,
    config: Config,
    health: SchedulerHealth,
    stop_event: threading.Event,
    *,
    interval: int = TICK_INTERVAL_SECONDS,
) -> None:
    health.started_at = datetime.now(UTC)
    logger.info("Scheduler started (tick interval=%ds)", interval)

    # Reconcile on startup so occurrences due during downtime are handled
    try:
        _tick(engine, config, health)
    except Exception as exc:
        health.last_error_at = datetime.now(UTC)
        health.last_error = str(exc)
        health.errors += 1
        logger.exception("Scheduler startup tick error")

    while not stop_event.wait(interval):
        try:
            _tick(engine, config, health)
        except Exception as exc:
            health.last_error_at = datetime.now(UTC)
            health.last_error = str(exc)
            health.errors += 1
            logger.exception("Scheduler tick error")

    logger.info("Scheduler stopped")
