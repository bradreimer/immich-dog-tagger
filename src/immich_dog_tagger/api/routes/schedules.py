from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from immich_dog_tagger.api.dependencies import (
    get_job_service,
    get_schedule_repository,
    get_schedule_service,
)
from immich_dog_tagger.api.schemas import (
    ScheduleCreateRequest,
    ScheduleResponse,
    ScheduleRunResponse,
    ScheduleUpdateRequest,
)
from immich_dog_tagger.services.jobs import PipelineJobService
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


@router.post("/{schedule_id}/enable", response_model=ScheduleResponse)
def enable_schedule(
    schedule_id: int,
    repository: Annotated[PipelineScheduleRepository, Depends(get_schedule_repository)],
    service: Annotated[PipelineScheduleService, Depends(get_schedule_service)],
):
    schedule = repository.get(schedule_id)

    if schedule is None:
        raise HTTPException(status_code=404, detail=f"Schedule {schedule_id} not found")

    return ScheduleResponse.from_schedule(service.enable(schedule))


@router.post("/{schedule_id}/disable", response_model=ScheduleResponse)
def disable_schedule(
    schedule_id: int,
    repository: Annotated[PipelineScheduleRepository, Depends(get_schedule_repository)],
    service: Annotated[PipelineScheduleService, Depends(get_schedule_service)],
):
    schedule = repository.get(schedule_id)

    if schedule is None:
        raise HTTPException(status_code=404, detail=f"Schedule {schedule_id} not found")

    return ScheduleResponse.from_schedule(service.disable(schedule))


@router.post("/{schedule_id}/run-now", response_model=ScheduleRunResponse)
def run_schedule_now(
    schedule_id: int,
    repository: Annotated[PipelineScheduleRepository, Depends(get_schedule_repository)],
    job_service: Annotated[PipelineJobService, Depends(get_job_service)],
):
    schedule = repository.get(schedule_id)

    if schedule is None:
        raise HTTPException(status_code=404, detail=f"Schedule {schedule_id} not found")

    job = job_service.create_job(operation=schedule.operation)
    return ScheduleRunResponse.from_job(job)
