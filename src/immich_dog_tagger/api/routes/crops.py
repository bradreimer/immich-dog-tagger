from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from immich_dog_tagger.api.dependencies import get_session
from immich_dog_tagger.models import Crop

router = APIRouter(
    prefix="/crops",
)


@router.get("/{crop_id}")
def crop(
    crop_id: int,
    session: Annotated[Session, Depends(get_session)],
):
    crop = session.get(
        Crop,
        crop_id,
    )

    if crop is None:
        raise HTTPException(
            status_code=404,
            detail=f"Crop {crop_id} not found",
        )

    return FileResponse(
        crop.path,
        media_type="image/jpeg",
    )
