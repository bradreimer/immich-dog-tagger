from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response

from immich_dog_tagger.api.dependencies import (
    get_immich_client,
    get_photo_lookup_service,
)
from immich_dog_tagger.api.schemas import PhotoLookupResponse
from immich_dog_tagger.immich import ImmichClient, ImmichDownloadError
from immich_dog_tagger.services.photo_lookup import PhotoLookupService

router = APIRouter(
    prefix="/photo-lookup",
)


@router.get("/{immich_asset_id}", response_model=PhotoLookupResponse)
def photo_lookup(
    immich_asset_id: str,
    service: Annotated[PhotoLookupService, Depends(get_photo_lookup_service)],
):
    lookup = service.get(immich_asset_id)

    if lookup is None:
        raise HTTPException(
            status_code=404,
            detail=f"No scanned photo found for Immich asset {immich_asset_id}",
        )

    return PhotoLookupResponse.from_lookup(lookup)


@router.get("/{immich_asset_id}/image")
def photo_lookup_image(
    immich_asset_id: str,
    service: Annotated[PhotoLookupService, Depends(get_photo_lookup_service)],
    client: Annotated[ImmichClient, Depends(get_immich_client)],
):
    # Looked up here too (not just by the sibling metadata endpoint) so a
    # request for an asset this instance has never scanned gets the same 404
    # as the metadata endpoint rather than an opaque Immich error.
    lookup = service.get(immich_asset_id)

    if lookup is None:
        raise HTTPException(
            status_code=404,
            detail=f"No scanned photo found for Immich asset {immich_asset_id}",
        )

    try:
        # Immich's full-size preview, not the original: always JPEG, so
        # browsers can render it regardless of the original's format (issue
        # #206 -- HEIC originals served as-is are unrenderable in <img>).
        content = client.download_asset_preview(immich_asset_id)
    except ImmichDownloadError as e:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch photo from Immich: {e}",
        ) from e

    return Response(
        content=content,
        media_type="image/jpeg",
    )
