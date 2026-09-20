import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from immich_dog_tagger.enums import PipelineOperation
from immich_dog_tagger.models import PipelineSchedule

# Operations that touch Immich (ADR-006) and so can be pinned to a specific
# configured account (issue #346). Everything else is local-only and never
# takes an account_id -- there is no "which Immich library" for detect/
# classify/reclassify/learn/embed/reembed to be scoped to.
ACCOUNT_SCOPED_OPERATIONS = frozenset(
    {
        PipelineOperation.SCAN,
        PipelineOperation.SYNC,
        PipelineOperation.FULL_PIPELINE,
    }
)


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
        account_id: int | None = None,
    ) -> PipelineSchedule:
        schedule = PipelineSchedule(
            name=name,
            operation=operation,
            expression=expression,
            timezone_name=timezone_name,
            enabled=enabled,
            account_id=account_id,
        )
        self.session.add(schedule)
        self.session.flush()
        return schedule

    def get(self, schedule_id: int) -> PipelineSchedule | None:
        return self.session.get(PipelineSchedule, schedule_id)

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
        account_id: int | None = None,
    ) -> PipelineSchedule:
        self._validate_operation(operation)
        self._validate_expression(expression)
        self._validate_account(operation, account_id)
        schedule = PipelineScheduleRepository(self.session).create(
            name=name,
            operation=operation,
            expression=expression,
            timezone_name=timezone_name,
            enabled=enabled,
            account_id=account_id,
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
        account_id: int | None = ...,
    ) -> PipelineSchedule:
        if name is not None:
            schedule.name = name
        if operation is not None:
            self._validate_operation(operation)
            schedule.operation = operation
        if expression is not None:
            self._validate_expression(expression)
            schedule.expression = expression
        if timezone_name is not None:
            schedule.timezone_name = timezone_name
        if enabled is not None:
            schedule.enabled = enabled
        # account_id's "unset" sentinel is `...`, not `None` -- unlike every
        # other field here, `None` is a real, meaningful value (this
        # schedule is not pinned to a specific account) that a caller must
        # be able to set explicitly, not just leave alone.
        if account_id is not ...:
            self._validate_account(schedule.operation, account_id)
            schedule.account_id = account_id
        self.session.commit()
        self.session.refresh(schedule)
        return schedule

    @staticmethod
    def _validate_account(
        operation: PipelineOperation,
        account_id: int | None,
    ) -> None:
        if account_id is not None and operation not in ACCOUNT_SCOPED_OPERATIONS:
            raise ValueError(
                f"{operation.value} is local-only and cannot be pinned to an account"
            )

    def enable(self, schedule: PipelineSchedule) -> PipelineSchedule:
        self._validate_operation(schedule.operation)
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
    def _validate_operation(operation: PipelineOperation) -> None:
        if operation == PipelineOperation.LEARN:
            raise ValueError(
                "Learn cannot be scheduled: it requires a specific identity and reference "
                "directory that a schedule has no way to supply. Review corrections are "
                "already learned immediately when reviewed -- there is nothing left for a "
                "scheduled Learn job to do."
            )

    @staticmethod
    def _validate_expression(expression: str) -> None:
        parts = expression.split()
        if len(parts) != 5:
            raise ValueError("Invalid schedule expression")

        if not all(re.fullmatch(r"[\*0-9,-/]+", part) for part in parts):
            raise ValueError("Invalid schedule expression")
