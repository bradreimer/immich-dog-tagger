from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from immich_dog_tagger.api.dependencies import get_dog_service
from immich_dog_tagger.api.schemas import (
    DogCreateRequest,
    DogMergeRequest,
    DogMergeResponse,
    DogResponse,
    DogUpdateRequest,
)
from immich_dog_tagger.services.dogs import DogService

router = APIRouter(
    prefix="/dogs",
)


@router.get(
    "",
    response_model=list[DogResponse],
)
def list_dogs(
    service: Annotated[DogService, Depends(get_dog_service)],
    include_inactive: bool = Query(True),
):
    return [
        DogResponse.from_identity(identity)
        for identity in service.list_dogs(include_inactive=include_inactive)
    ]


@router.post(
    "",
    response_model=DogResponse,
)
def create_dog(
    request: DogCreateRequest,
    service: Annotated[DogService, Depends(get_dog_service)],
):
    try:
        return DogResponse.from_identity(
            service.create_dog(request.name, request.species)
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put(
    "/{dog_id}",
    response_model=DogResponse,
)
def update_dog(
    dog_id: int,
    request: DogUpdateRequest,
    service: Annotated[DogService, Depends(get_dog_service)],
):
    try:
        return DogResponse.from_identity(service.rename_dog(dog_id, request.name))
    except ValueError as exc:
        status_code = 404 if "not found" in str(exc).lower() else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@router.post(
    "/{dog_id}/activate",
    response_model=DogResponse,
)
def activate_dog(
    dog_id: int,
    service: Annotated[DogService, Depends(get_dog_service)],
):
    try:
        return DogResponse.from_identity(service.activate_dog(dog_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/{dog_id}/merge",
    response_model=DogMergeResponse,
)
def merge_dog(
    dog_id: int,
    request: DogMergeRequest,
    service: Annotated[DogService, Depends(get_dog_service)],
):
    """
    Merge the identity at `dog_id` (the source) into `request.target_id`.

    Destructive and effectively irreversible: it re-attributes every
    classification and reference example the source owned. The UI confirms
    before calling this.
    """
    try:
        summary = service.merge_dogs(dog_id, request.target_id)
    except ValueError as exc:
        status_code = 404 if "not found" in str(exc).lower() else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc

    source = service.get_dog(summary.source_id)
    target = service.get_dog(summary.target_id)

    return DogMergeResponse(
        source=DogResponse.from_identity(source),
        target=DogResponse.from_identity(target),
        classifications_reassigned=summary.classifications_reassigned,
        examples_reassigned=summary.examples_reassigned,
        examples_discarded=summary.examples_discarded,
        occurrences_reassigned=summary.occurrences_reassigned,
    )


@router.delete(
    "/{dog_id}",
    response_model=DogResponse,
)
def deactivate_dog(
    dog_id: int,
    service: Annotated[DogService, Depends(get_dog_service)],
):
    try:
        return DogResponse.from_identity(service.deactivate_dog(dog_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
