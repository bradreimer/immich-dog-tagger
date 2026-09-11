from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from immich_dog_tagger.database import create_database
from immich_dog_tagger.enums import PipelineOperation
from immich_dog_tagger.services.schedules import (
    PipelineScheduleRepository,
    PipelineScheduleService,
)


def test_schedule_can_persist_and_be_retrieved(engine):
    with Session(engine) as session:
        service = PipelineScheduleService(session)
        schedule = service.create_schedule(
            name="Daily full pipeline",
            operation=PipelineOperation.FULL_PIPELINE,
            expression="0 * * * *",
            timezone_name="UTC",
        )
        schedule_id = schedule.id

    with Session(engine) as session:
        repository = PipelineScheduleRepository(session)
        persisted = repository.get(schedule_id)

        assert persisted is not None
        assert persisted.name == "Daily full pipeline"
        assert persisted.operation is PipelineOperation.FULL_PIPELINE
        assert persisted.expression == "0 * * * *"
        assert persisted.timezone_name == "UTC"
        assert persisted.enabled is True
        assert persisted.next_run_at is None
        assert persisted.last_run_at is None


def test_schedule_rejects_invalid_expression(engine):
    with Session(engine) as session:
        service = PipelineScheduleService(session)

        with pytest.raises(ValueError, match="Invalid schedule expression"):
            service.create_schedule(
                name="Bad schedule",
                operation=PipelineOperation.SYNC,
                expression="invalid",
                timezone_name="UTC",
            )


def test_schedule_state_survives_database_reopen(tmp_path: Path):
    engine = create_database(tmp_path)

    with Session(engine) as session:
        service = PipelineScheduleService(session)
        schedule = service.create_schedule(
            name="Nightly reclassify",
            operation=PipelineOperation.RECLASSIFY,
            expression="30 2 * * *",
            timezone_name="UTC",
        )
        schedule_id = schedule.id

    reopened_engine = create_database(tmp_path)

    with Session(reopened_engine) as session:
        repository = PipelineScheduleRepository(session)
        persisted = repository.get(schedule_id)

        assert persisted is not None
        assert persisted.name == "Nightly reclassify"
        assert persisted.enabled is True


def test_schedule_rejects_learn_operation_on_create(engine):
    with Session(engine) as session:
        service = PipelineScheduleService(session)

        with pytest.raises(ValueError, match="Learn cannot be scheduled"):
            service.create_schedule(
                name="Nightly learn",
                operation=PipelineOperation.LEARN,
                expression="30 2 * * *",
                timezone_name="UTC",
            )


def test_schedule_rejects_learn_operation_on_update(engine):
    with Session(engine) as session:
        service = PipelineScheduleService(session)
        schedule = service.create_schedule(
            name="Nightly reclassify",
            operation=PipelineOperation.RECLASSIFY,
            expression="30 2 * * *",
            timezone_name="UTC",
        )

        with pytest.raises(ValueError, match="Learn cannot be scheduled"):
            service.update_schedule(schedule, operation=PipelineOperation.LEARN)


def test_schedule_rejects_enabling_a_learn_schedule(engine):
    with Session(engine) as session:
        service = PipelineScheduleService(session)
        repository = PipelineScheduleRepository(session)
        # A LEARN schedule can only exist here by bypassing the service (e.g.
        # a row left over from before scheduling LEARN was rejected).
        schedule = repository.create(
            name="Nightly learn",
            operation=PipelineOperation.LEARN,
            expression="30 2 * * *",
            timezone_name="UTC",
            enabled=False,
        )
        session.commit()

        with pytest.raises(ValueError, match="Learn cannot be scheduled"):
            service.enable(schedule)


def test_database_startup_disables_existing_learn_schedules(tmp_path: Path):
    engine = create_database(tmp_path)

    with Session(engine) as session:
        repository = PipelineScheduleRepository(session)
        schedule = repository.create(
            name="Nightly learn",
            operation=PipelineOperation.LEARN,
            expression="30 2 * * *",
            timezone_name="UTC",
            enabled=True,
        )
        schedule_id = schedule.id
        session.commit()

    reopened_engine = create_database(tmp_path)

    with Session(reopened_engine) as session:
        repository = PipelineScheduleRepository(session)
        persisted = repository.get(schedule_id)

        assert persisted is not None
        assert persisted.enabled is False
