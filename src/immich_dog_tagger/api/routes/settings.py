from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from immich_dog_tagger.api.dependencies import get_config, get_session
from immich_dog_tagger.api.schemas import SettingsResponse
from immich_dog_tagger.config import Config
from immich_dog_tagger.models import Asset

router = APIRouter(
    prefix="/settings",
)


@router.get(
    "",
    response_model=SettingsResponse,
)
def get_settings(
    session: Annotated[Session, Depends(get_session)],
    config: Annotated[Config, Depends(get_config)],
):
    scanned_image_count = session.execute(select(func.count(Asset.id))).scalar_one()

    return SettingsResponse(
        immich_url=config.immich_url,
        scanned_image_count=scanned_image_count,
    )
