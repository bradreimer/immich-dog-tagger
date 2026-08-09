from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from immich_dog_tagger.api.dependencies import (
    get_schedule_repository,
    get_schedule_service,
)
from immich_dog_tagger.api.schemas import (
    ScheduleCreateRequest,
    ScheduleResponse,
    ScheduleUpdateRequest,
)
from immich_dog_tagger.services.schedules import (
    PipelineScheduleRepository,
    PipelineScheduleService,
)

router = APIRouter(prefix="/schedules")


@router.get("", response_model=list[ScheduleResponse])
def list_schedules(
    repository: Annotated[PipelineScheduleRepository, Depends(get_schedule_repository)],
    limit: int = Query(100, ge=1, le=500),
):
    schedules = repository.list_all()[:limit]
    return [ScheduleResponse.from_schedule(schedule) for schedule in schedules]


@router.get("/{schedule_id}", response_model=ScheduleResponse)
def get_schedule(
    schedule_id: int,
    repository: Annotated[PipelineScheduleRepository, Depends(get_schedule_repository)],
):
    schedule = repository.get(schedule_id)

    if schedule is None:
        raise HTTPException(status_code=404, detail=f"Schedule {schedule_id} not found")

    return ScheduleResponse.from_schedule(schedule)


@router.post("", response_model=ScheduleResponse, status_code=201)
def create_schedule(
    request: ScheduleCreateRequest,
    service: Annotated[PipelineScheduleService, Depends(get_schedule_service)],
):
    try:
        schedule = service.create_schedule(
            name=request.name,
            operation=request.operation,
            expression=request.expression,
            timezone_name=request.timezone_name,
            enabled=request.enabled,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return ScheduleResponse.from_schedule(schedule)


@router.put("/{schedule_id}", response_model=ScheduleResponse)
def update_schedule(
    schedule_id: int,
    request: ScheduleUpdateRequest,
    repository: Annotated[PipelineScheduleRepository, Depends(get_schedule_repository)],
    service: Annotated[PipelineScheduleService, Depends(get_schedule_service)],
):
    schedule = repository.get(schedule_id)

    if schedule is None:
        raise HTTPException(status_code=404, detail=f"Schedule {schedule_id} not found")

    try:
        schedule = service.update_schedule(
            schedule,
            name=request.name,
            operation=request.operation,
            expression=request.expression,
            timezone_name=request.timezone_name,
            enabled=request.enabled,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return ScheduleResponse.from_schedule(schedule)
