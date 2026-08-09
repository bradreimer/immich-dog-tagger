from datetime import UTC, datetime

from sqlalchemy.orm import Session

from immich_dog_tagger.enums import PipelineJobStatus, PipelineOperation
from immich_dog_tagger.models import PipelineSchedule
from immich_dog_tagger.services.job_runner import PipelineJobRunner
from immich_dog_tagger.services.jobs import PipelineJobRepository, PipelineJobService
from immich_dog_tagger.services.scheduler import SchedulerService
from immich_dog_tagger.services.schedules import PipelineScheduleService


class FixedClock:
    def __init__(self, now: datetime):
        self._now = now

    def now(self) -> datetime:
        return self._now


def make_schedule(
    session: Session, *, expression: str, enabled: bool = True
) -> PipelineSchedule:
    service = PipelineScheduleService(session)
    return service.create_schedule(
        name="Hourly",
        operation=PipelineOperation.FULL_PIPELINE,
        expression=expression,
        timezone_name="UTC",
        enabled=enabled,
    )


def test_scheduler_detects_due_schedule(engine):
    with Session(engine) as session:
        schedule = make_schedule(session, expression="0 * * * *")
        clock = FixedClock(datetime(2026, 1, 1, 12, 0, tzinfo=UTC))
        scheduler = SchedulerService(session, clock=clock)

        due = scheduler.due_schedules()

        assert len(due) == 1
        assert due[0].id == schedule.id


def test_scheduler_ignores_disabled_schedule(engine):
    with Session(engine) as session:
        make_schedule(session, expression="0 * * * *", enabled=False)
        clock = FixedClock(datetime(2026, 1, 1, 12, 0, tzinfo=UTC))
        scheduler = SchedulerService(session, clock=clock)

        assert scheduler.due_schedules() == []


def test_scheduler_calculates_next_run(engine):
    with Session(engine) as session:
        schedule = make_schedule(session, expression="0 * * * *")
        clock = FixedClock(datetime(2026, 1, 1, 12, 0, tzinfo=UTC))
        scheduler = SchedulerService(session, clock=clock)

        next_run = scheduler.next_run_for(schedule)

        assert next_run == datetime(2026, 1, 1, 13, 0, tzinfo=UTC)


def test_scheduler_creates_and_runs_due_schedule_through_job_runner(engine):
    with Session(engine) as session:
        schedule = make_schedule(session, expression="0 * * * *")
        clock = FixedClock(datetime(2026, 1, 1, 12, 0, tzinfo=UTC))

        repository = PipelineJobRepository(session)
        job_service = PipelineJobService(session, repository=repository)
        runner = PipelineJobRunner(
            repository,
            job_service,
            handlers={PipelineOperation.FULL_PIPELINE: lambda progress: {"ok": True}},
        )
        scheduler = SchedulerService(
            session,
            clock=clock,
            job_service=job_service,
            runner=runner,
        )

        created_jobs = scheduler.dispatch_due_schedules()

        assert len(created_jobs) == 1
        assert created_jobs[0].schedule_id == schedule.id
        assert created_jobs[0].status is PipelineJobStatus.COMPLETED
        assert created_jobs[0].operation is PipelineOperation.FULL_PIPELINE


def test_scheduler_prevents_duplicate_jobs_for_same_due_occurrence(engine):
    with Session(engine) as session:
        make_schedule(session, expression="0 * * * *")
        clock = FixedClock(datetime(2026, 1, 1, 12, 0, tzinfo=UTC))

        scheduler = SchedulerService(session, clock=clock)

        first_pass = scheduler.dispatch_due_schedules()
        second_pass = scheduler.dispatch_due_schedules()

        assert len(first_pass) == 1
        assert second_pass == []
