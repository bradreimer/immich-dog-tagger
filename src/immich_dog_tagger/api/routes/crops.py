from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import Engine

from immich_dog_tagger.api.dependencies import get_engine, get_false_positive_service
from immich_dog_tagger.services.false_positives import (
    FalsePositiveService,
    get_viewable_crop_path,
)

router = APIRouter(
    prefix="/crops",
)


@router.get("/{crop_id}")
def crop(
    crop_id: int,
    engine: Annotated[Engine, Depends(get_engine)],
):
    # Looks the path up through its own short-lived session rather than a
    # request-scoped `Depends(get_session)` -- see
    # `get_viewable_crop_path`'s docstring (issue #277): a DB session tied
    # to this request would otherwise stay checked out of the pool for as
    # long as the image takes to stream back, not just for this lookup.
    try:
        path = get_viewable_crop_path(engine, crop_id)
    except ValueError as e:
        raise HTTPException(
            status_code=404,
            detail=str(e),
        ) from e

    return FileResponse(
        path,
        media_type="image/jpeg",
    )


@router.post("/{crop_id}/not-animal")
def mark_crop_not_animal(
    crop_id: int,
    service: Annotated[FalsePositiveService, Depends(get_false_positive_service)],
):
    try:
        service.mark(crop_id)
    except ValueError as e:
        raise HTTPException(
            status_code=404,
            detail=str(e),
        ) from e

    return {"crop_id": crop_id, "not_animal": True}


@router.delete("/{crop_id}/not-animal")
def unmark_crop_not_animal(
    crop_id: int,
    service: Annotated[FalsePositiveService, Depends(get_false_positive_service)],
):
    try:
        service.unmark(crop_id)
    except ValueError as e:
        raise HTTPException(
            status_code=404,
            detail=str(e),
        ) from e

    return {"crop_id": crop_id, "not_animal": False}
