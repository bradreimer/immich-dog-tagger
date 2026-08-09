import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from immich_dog_tagger.enums import PipelineOperation
from immich_dog_tagger.models import PipelineSchedule


class PipelineScheduleRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(
        self,
        *,
        name: str,
        operation: PipelineOperation,
        expression: str,
        timezone_name: str,
        enabled: bool = True,
    ) -> PipelineSchedule:
        schedule = PipelineSchedule(
            name=name,
            operation=operation,
            expression=expression,
            timezone_name=timezone_name,
            enabled=enabled,
        )
        self.session.add(schedule)
        self.session.flush()
        return schedule

    def get(self, schedule_id: int) -> PipelineSchedule | None:
        return self.session.get(PipelineSchedule, schedule_id)

    def list_enabled(self) -> list[PipelineSchedule]:
        return self.session.scalars(
            select(PipelineSchedule).where(PipelineSchedule.enabled.is_(True))
        ).all()

    def list_all(self) -> list[PipelineSchedule]:
        return self.session.scalars(select(PipelineSchedule)).all()


class PipelineScheduleService:
    def __init__(self, session: Session):
        self.session = session

    def create_schedule(
        self,
        *,
        name: str,
        operation: PipelineOperation,
        expression: str,
        timezone_name: str,
        enabled: bool = True,
    ) -> PipelineSchedule:
        self._validate_expression(expression)
        schedule = PipelineScheduleRepository(self.session).create(
            name=name,
            operation=operation,
            expression=expression,
            timezone_name=timezone_name,
            enabled=enabled,
        )
        self.session.commit()
        self.session.refresh(schedule)
        return schedule

    def update_schedule(
        self,
        schedule: PipelineSchedule,
        *,
        name: str | None = None,
        operation: PipelineOperation | None = None,
        expression: str | None = None,
        timezone_name: str | None = None,
        enabled: bool | None = None,
    ) -> PipelineSchedule:
        if name is not None:
            schedule.name = name
        if operation is not None:
            schedule.operation = operation
        if expression is not None:
            self._validate_expression(expression)
            schedule.expression = expression
        if timezone_name is not None:
            schedule.timezone_name = timezone_name
        if enabled is not None:
            schedule.enabled = enabled
        self.session.commit()
        self.session.refresh(schedule)
        return schedule

    def enable(self, schedule: PipelineSchedule) -> PipelineSchedule:
        schedule.enabled = True
        self.session.commit()
        self.session.refresh(schedule)
        return schedule

    def disable(self, schedule: PipelineSchedule) -> PipelineSchedule:
        schedule.enabled = False
        self.session.commit()
        self.session.refresh(schedule)
        return schedule

    @staticmethod
    def _validate_expression(expression: str) -> None:
        parts = expression.split()
        if len(parts) != 5:
            raise ValueError("Invalid schedule expression")

        if not all(re.fullmatch(r"[\*0-9,-/]+", part) for part in parts):
            raise ValueError("Invalid schedule expression")
