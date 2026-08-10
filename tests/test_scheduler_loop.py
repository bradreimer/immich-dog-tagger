"""Tests for scheduler failure isolation, health tracking, and the background loop."""

from __future__ import annotations

import threading
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from immich_dog_tagger.enums import PipelineJobStatus, PipelineOperation
from immich_dog_tagger.services.job_runner import PipelineJobRunner
from immich_dog_tagger.services.jobs import PipelineJobRepository, PipelineJobService
from immich_dog_tagger.services.scheduler import SchedulerService
from immich_dog_tagger.services.scheduler_loop import SchedulerHealth, run_scheduler
from immich_dog_tagger.services.schedules import PipelineScheduleService


class FixedClock:
    def __init__(self, now: datetime):
        self._now = now

    def now(self) -> datetime:
        return self._now


def make_schedule(
    session: Session,
    *,
    name: str = "Test",
    expression: str = "0 * * * *",
    enabled: bool = True,
):
    service = PipelineScheduleService(session)
    return service.create_schedule(
        name=name,
        operation=PipelineOperation.FULL_PIPELINE,
        expression=expression,
        timezone_name="UTC",
        enabled=enabled,
    )


# ---------------------------------------------------------------------------
# Failure isolation
# ---------------------------------------------------------------------------


def test_failing_schedule_does_not_prevent_other_schedules_from_running(engine):
    """One erroring schedule must not stop sibling schedules from dispatching."""
    with Session(engine) as session:
        make_schedule(session, name="Broken")
        make_schedule(session, name="Healthy")

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

        # Patch _dispatch_schedule so the first call raises
        original_dispatch = scheduler._dispatch_schedule
        call_count = [0]

        def patched_dispatch(schedule):
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("simulated schedule dispatch error")
            return original_dispatch(schedule)

        scheduler._dispatch_schedule = patched_dispatch

        created = scheduler.dispatch_due_schedules()

        # Despite the first schedule failing, the second should have produced a job
        assert len(created) == 1
        assert created[0].status is PipelineJobStatus.COMPLETED


# ---------------------------------------------------------------------------
# SchedulerHealth
# ---------------------------------------------------------------------------


def test_health_is_healthy_with_no_errors():
    h = SchedulerHealth()
    h.last_tick_at = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    assert h.healthy is True


def test_health_is_unhealthy_when_error_after_last_tick():
    h = SchedulerHealth()
    h.last_tick_at = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    h.last_error_at = datetime(2026, 1, 1, 12, 5, tzinfo=UTC)
    assert h.healthy is False


def test_health_is_healthy_when_tick_after_error():
    h = SchedulerHealth()
    h.last_error_at = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    h.last_tick_at = datetime(2026, 1, 1, 12, 5, tzinfo=UTC)
    assert h.healthy is True


def test_health_as_dict_contains_expected_keys():
    h = SchedulerHealth()
    d = h.as_dict()
    assert {
        "healthy",
        "ticks",
        "errors",
        "started_at",
        "last_tick_at",
        "last_error_at",
        "last_error",
    } <= d.keys()


# ---------------------------------------------------------------------------
# Background loop
# ---------------------------------------------------------------------------


def test_scheduler_loop_ticks_and_stops(engine, monkeypatch, tmp_path):
    """run_scheduler should tick at least once and stop cleanly."""
    monkeypatch.setenv("STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("YOLO_MODEL", str(tmp_path / "yolo11n.pt"))

    from immich_dog_tagger.config import load_config

    config = load_config(load_env_file=False)

    health = SchedulerHealth()
    stop_event = threading.Event()

    thread = threading.Thread(
        target=run_scheduler,
        args=(engine, config, health, stop_event),
        kwargs={"interval": 3600},  # long interval so only startup tick fires
        daemon=True,
    )
    thread.start()
    thread.join(timeout=5)

    stop_event.set()
    thread.join(timeout=5)

    # Startup tick should have happened
    assert health.ticks >= 1
    assert health.started_at is not None


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------


def test_health_endpoint_returns_scheduler_status(api_client):
    response = api_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    # scheduler key is present (may be None if lifespan not triggered by TestClient)
    assert "scheduler" in data
