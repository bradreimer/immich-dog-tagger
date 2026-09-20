from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import Engine

from immich_dog_tagger.api.dependencies import (
    get_engine,
    get_false_positive_service,
    get_manual_detection_assignment_service,
)
from immich_dog_tagger.api.schemas import (
    DetectionAssignRequest,
    DetectionAssignResponse,
)
from immich_dog_tagger.services.false_positives import (
    FalsePositiveService,
    get_viewable_crop_path,
)
from immich_dog_tagger.services.manual_detection_assignment import (
    ManualDetectionAssignmentService,
)

router = APIRouter(
    prefix="/crops",
)


def _assignment_error(e: ValueError) -> HTTPException:
    status_code = 404 if "not found" in str(e).lower() else 400

    return HTTPException(status_code=status_code, detail=str(e))


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


@router.post("/{crop_id}/assign", response_model=DetectionAssignResponse)
def assign_crop(
    crop_id: int,
    request: DetectionAssignRequest,
    service: Annotated[
        ManualDetectionAssignmentService,
        Depends(get_manual_detection_assignment_service),
    ],
):
    # Issue #353: give a crop that already exists but was never classified
    # (e.g. after Repair re-detects a photo without a classify pass
    # producing a CropClassification for every crop) its first species/
    # identity decision -- the crop-ful counterpart of assign_detection's
    # crop-less case in photo_lookup.py.
    try:
        crop = service.assign_crop(crop_id, request.species, request.identity)
    except ValueError as e:
        raise _assignment_error(e) from e

    return DetectionAssignResponse.from_crop(crop)
