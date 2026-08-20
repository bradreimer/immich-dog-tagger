"""
Photos the detector missed, and the manual tags that rescue them
(issue #147).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from immich_dog_tagger.api.dependencies import get_manual_tag_service
from immich_dog_tagger.api.schemas import (
    ManualAssetTagRequest,
    ManualAssetTagResponse,
    UndetectedAssetPageResponse,
)
from immich_dog_tagger.services.manual_tags import ManualTagService

router = APIRouter(
    prefix="/undetected",
)


@router.get(
    "",
    response_model=UndetectedAssetPageResponse,
)
def undetected_assets(
    service: Annotated[ManualTagService, Depends(get_manual_tag_service)],
    limit: int = Query(24, ge=1, le=100),
    offset: int = Query(0, ge=0),
    tagged: bool | None = Query(None),
):
    """
    Photos detection has finished with that produced no crop -- the
    population #146's coverage figures count, listed so it can be acted on.
    """
    return UndetectedAssetPageResponse.from_page(
        service.undetected_assets(
            limit=limit,
            offset=offset,
            tagged=tagged,
        )
    )


@router.post(
    "/{asset_id}/tags",
    response_model=ManualAssetTagResponse,
)
def add_manual_tag(
    asset_id: int,
    request: ManualAssetTagRequest,
    service: Annotated[ManualTagService, Depends(get_manual_tag_service)],
):
    """
    Record that this photo contains the named pet.

    Reaches the pet's Immich album on the next operator-triggered sync
    (ADR-006), and nothing else: it is never a reference example, because
    there is no crop or embedding behind it to learn from.
    """
    try:
        service.tag(asset_id, request.identity, request.species)
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e),
        ) from e

    return ManualAssetTagResponse(
        asset_id=asset_id,
        identities=[tag.identity for tag in service.tags_for(asset_id)],
    )


@router.delete(
    "/{asset_id}/tags",
    response_model=ManualAssetTagResponse,
)
def remove_manual_tag(
    asset_id: int,
    request: ManualAssetTagRequest,
    service: Annotated[ManualTagService, Depends(get_manual_tag_service)],
):
    """
    Undo a manual tag. The next sync removes the photo from that pet's
    album through the existing stale-membership diff.
    """
    if not service.untag(asset_id, request.identity, request.species):
        raise HTTPException(
            status_code=404,
            detail="No such manual tag",
        )

    return ManualAssetTagResponse(
        asset_id=asset_id,
        identities=[tag.identity for tag in service.tags_for(asset_id)],
    )
