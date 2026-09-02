import io
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response

from immich_dog_tagger.api.dependencies import (
    get_asset_repair_service,
    get_immich_client,
    get_photo_lookup_service,
)
from immich_dog_tagger.api.schemas import AssetRepairResponse, PhotoLookupResponse
from immich_dog_tagger.images import open_upright, to_jpeg_bytes
from immich_dog_tagger.immich import ImmichClient, ImmichDownloadError
from immich_dog_tagger.services.asset_repair import AssetRepairService
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
        content = client.download_asset(immich_asset_id)
    except ImmichDownloadError as e:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch photo from Immich: {e}",
        ) from e

    try:
        # Decoded and re-encoded through the same open_upright() path the
        # detector uses (issue #213), not served as-is or through Immich's
        # own preview/thumbnail pipeline: `Detection.x1/y1/x2/y2` were
        # computed against an open_upright()-decoded image, so the overlay
        # boxes only line up with what's displayed here if this is decoded
        # identically. Also transcodes to JPEG along the way, which is what
        # makes an unrenderable-in-<img> original (HEIC, issue #206) safe to
        # display without depending on Immich's independent transcoding
        # agreeing on orientation (it doesn't always -- see immich-app/
        # immich#24807 -- which is what broke the boxes when #206 switched
        # to it).
        image = open_upright(io.BytesIO(content))
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to decode photo from Immich: {e}",
        ) from e

    return Response(
        content=to_jpeg_bytes(image),
        media_type="image/jpeg",
    )


@router.post("/{immich_asset_id}/repair", response_model=AssetRepairResponse)
def repair_photo(
    immich_asset_id: str,
    service: Annotated[AssetRepairService, Depends(get_asset_repair_service)],
):
    # Forces this one asset back through download/detect/classify (issue
    # #226) -- a deliberate, per-photo action a human takes from Review or
    # Photo Lookup when a photo's detections look stale, not something run
    # automatically across the library. See AssetRepairService's docstring
    # for what this discards on an already-reviewed photo.
    try:
        result = service.repair(immich_asset_id)
    except ValueError as e:
        raise HTTPException(
            status_code=404,
            detail=str(e),
        ) from e

    return AssetRepairResponse.from_result(result)
