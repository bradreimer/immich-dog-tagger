from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from immich_dog_tagger.enums import PipelineOperation
from immich_dog_tagger.models import PipelineJob, PipelineSchedule
from immich_dog_tagger.services.job_execution import create_pipeline_job_runner
from immich_dog_tagger.services.job_runner import PipelineJobRunner
from immich_dog_tagger.services.jobs import PipelineJobRepository, PipelineJobService

logger = logging.getLogger(__name__)


class Clock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class SchedulerService:
    def __init__(
        self,
        session: Session,
        clock: Clock | None = None,
        job_service: PipelineJobService | None = None,
        runner: PipelineJobRunner | None = None,
        config: object | None = None,
    ):
        self.session = session
        self.clock = clock or SystemClock()
        self.job_service = job_service
        self.runner = runner
        self.config = config

    def due_schedules(self) -> list[PipelineSchedule]:
        now = self.clock.now()
        schedules = self.session.scalars(
            select(PipelineSchedule).where(
                PipelineSchedule.enabled.is_(True),
            )
        ).all()

        return [schedule for schedule in schedules if self._is_due(schedule, now)]

    def next_run_for(self, schedule: PipelineSchedule) -> datetime | None:
        now = self.clock.now()
        return self._next_run_after(schedule, now)

    def dispatch_due_schedules(self) -> list[PipelineJob]:
        created_jobs: list[PipelineJob] = []
        for schedule in self.due_schedules():
            try:
                job = self._dispatch_schedule(schedule)
                if job is not None:
                    created_jobs.append(job)
            except Exception:
                logger.exception(
                    "Failed to dispatch schedule %r (id=%s)", schedule.name, schedule.id
                )
        return created_jobs

    def _dispatch_schedule(self, schedule: PipelineSchedule) -> PipelineJob | None:
        if self._has_existing_job_for_schedule(schedule):
            return None

        job_service = self.job_service or PipelineJobService(self.session)
        runner = self.runner

        if runner is None:
            if self.config is not None:
                runner = create_pipeline_job_runner(self.session, self.config)
            else:
                runner = PipelineJobRunner(
                    PipelineJobRepository(self.session),
                    job_service,
                    handlers={PipelineOperation.FULL_PIPELINE: lambda progress: None},
                )

        job = job_service.create_job(operation=schedule.operation)
        job.schedule_id = schedule.id
        self.session.commit()
        self.session.refresh(job)
        logger.info(
            "Dispatching scheduled job for %r (schedule_id=%s, job_id=%s)",
            schedule.name,
            schedule.id,
            job.id,
        )
        runner.run_job(job.id)
        return job

    def reconcile_schedules(self) -> list[PipelineSchedule]:
        schedules = self.session.scalars(
            select(PipelineSchedule).where(PipelineSchedule.enabled.is_(True))
        ).all()
        for schedule in schedules:
            self._reconcile_schedule(schedule)
        return schedules

    def _reconcile_schedule(self, schedule: PipelineSchedule) -> None:
        if self._has_existing_job_for_schedule(schedule):
            return

        if self._is_due(schedule, self.clock.now()):
            self._dispatch_schedule(schedule)

    def _has_existing_job_for_schedule(self, schedule: PipelineSchedule) -> bool:
        return any(job.schedule_id == schedule.id for job in schedule.jobs)

    @staticmethod
    def _is_due(schedule: PipelineSchedule, now: datetime) -> bool:
        if not schedule.enabled:
            return False

        parts = schedule.expression.split()
        minute_expr, hour_expr, _day_of_month, _month, _day_of_week = parts
        minute_value = int(minute_expr) if minute_expr != "*" else now.minute
        hour_value = int(hour_expr) if hour_expr != "*" else now.hour
        return hour_value == now.hour and minute_value == now.minute

    @staticmethod
    def _next_run_after(schedule: PipelineSchedule, now: datetime) -> datetime | None:
        if not schedule.enabled:
            return None

        parts = schedule.expression.split()
        minute_expr, hour_expr, _day_of_month, _month, _day_of_week = parts
        now = now.astimezone(UTC) if now.tzinfo else now.replace(tzinfo=UTC)

        if minute_expr == "*":
            minute_value = now.minute
        else:
            minute_value = int(minute_expr)

        if hour_expr == "*":
            hour_value = now.hour
        else:
            hour_value = int(hour_expr)

        if hour_value != now.hour or minute_value != now.minute:
            return now.replace(
                hour=hour_value, minute=minute_value, second=0, microsecond=0
            )

        return now + timedelta(hours=1)
