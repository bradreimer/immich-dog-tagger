from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from immich_dog_tagger.api.dependencies import get_config, get_session
from immich_dog_tagger.api.schemas import (
    SettingsResponse,
    TaggingSensitivityRequest,
)
from immich_dog_tagger.config import Config
from immich_dog_tagger.models import Asset
from immich_dog_tagger.services.app_settings import AppSettingsService
from immich_dog_tagger.version import get_version

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
        immich_external_url=config.immich_link_base_url,
        scanned_image_count=scanned_image_count,
        version=get_version(),
        tagging_sensitivity=AppSettingsService(session).sensitivity(),
    )


@router.put(
    "/tagging-sensitivity",
    response_model=SettingsResponse,
)
def set_tagging_sensitivity(
    request: TaggingSensitivityRequest,
    session: Annotated[Session, Depends(get_session)],
    config: Annotated[Config, Depends(get_config)],
):
    """
    Change how cautious automatic tagging is (issue #149).

    Applies to the next classification or Reclassify. It never rewrites
    past predictions, and because it only moves the boundary for *derived*
    predictions it can never touch a reviewed label.
    """
    settings = AppSettingsService(session)
    settings.set_sensitivity(request.tagging_sensitivity)

    scanned_image_count = session.execute(select(func.count(Asset.id))).scalar_one()

    return SettingsResponse(
        immich_url=config.immich_url,
        immich_external_url=config.immich_link_base_url,
        scanned_image_count=scanned_image_count,
        version=get_version(),
        tagging_sensitivity=settings.sensitivity(),
    )
