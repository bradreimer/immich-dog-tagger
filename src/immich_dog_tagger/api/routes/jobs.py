from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from immich_dog_tagger.api.dependencies import (
    get_job_dispatcher,
    get_job_repository,
    get_job_service,
)
from immich_dog_tagger.api.schemas import JobCreateRequest, JobResponse
from immich_dog_tagger.services.job_dispatcher import PipelineJobDispatcher
from immich_dog_tagger.services.jobs import PipelineJobRepository, PipelineJobService

router = APIRouter(
    prefix="/jobs",
)


@router.get(
    "",
    response_model=list[JobResponse],
)
def list_jobs(
    repository: Annotated[PipelineJobRepository, Depends(get_job_repository)],
    limit: int = Query(100, ge=1, le=500),
):
    jobs = repository.list_recent(limit=limit)
    return [JobResponse.from_job(job) for job in jobs]


@router.get(
    "/{job_id}",
    response_model=JobResponse,
)
def get_job(
    job_id: int,
    repository: Annotated[PipelineJobRepository, Depends(get_job_repository)],
):
    job = repository.get(job_id)

    if job is None:
        raise HTTPException(
            status_code=404,
            detail=f"Job {job_id} not found",
        )

    return JobResponse.from_job(job)


@router.post(
    "",
    response_model=JobResponse,
    status_code=201,
)
def create_job(
    request: JobCreateRequest,
    service: Annotated[PipelineJobService, Depends(get_job_service)],
    dispatcher: Annotated[PipelineJobDispatcher, Depends(get_job_dispatcher)],
):
    job = service.create_job(operation=request.operation)

    if request.start:
        dispatcher.trigger()

    return JobResponse.from_job(job)


@router.post(
    "/{job_id}/cancel",
    response_model=JobResponse,
)
def cancel_job(
    job_id: int,
    repository: Annotated[PipelineJobRepository, Depends(get_job_repository)],
    service: Annotated[PipelineJobService, Depends(get_job_service)],
):
    job = repository.get(job_id)

    if job is None:
        raise HTTPException(
            status_code=404,
            detail=f"Job {job_id} not found",
        )

    try:
        job = service.cancel_job(job)
    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    return JobResponse.from_job(job)
