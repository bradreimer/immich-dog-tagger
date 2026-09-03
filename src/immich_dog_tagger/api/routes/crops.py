from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from immich_dog_tagger.api.dependencies import get_false_positive_service
from immich_dog_tagger.services.false_positives import FalsePositiveService

router = APIRouter(
    prefix="/crops",
)


@router.get("/{crop_id}")
def crop(
    crop_id: int,
    service: Annotated[FalsePositiveService, Depends(get_false_positive_service)],
):
    try:
        crop = service.get_viewable(crop_id)
    except ValueError as e:
        raise HTTPException(
            status_code=404,
            detail=str(e),
        ) from e

    return FileResponse(
        crop.path,
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
