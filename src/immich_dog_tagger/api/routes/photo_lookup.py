import io
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response

from immich_dog_tagger.api.dependencies import (
    get_asset_repair_service,
    get_immich_client,
    get_manual_detection_assignment_service,
    get_photo_lookup_service,
)
from immich_dog_tagger.api.schemas import (
    AssetRepairResponse,
    DetectionAssignRequest,
    DetectionAssignResponse,
    PhotoLookupResponse,
)
from immich_dog_tagger.images import open_upright, to_jpeg_bytes
from immich_dog_tagger.immich import ImmichClient, ImmichDownloadError
from immich_dog_tagger.services.asset_repair import AssetRepairService
from immich_dog_tagger.services.manual_detection_assignment import (
    ManualDetectionAssignmentService,
)
from immich_dog_tagger.services.photo_lookup import PhotoLookupService

router = APIRouter(
    prefix="/photo-lookup",
)


def _require_detection_on_asset(
    lookup_service: PhotoLookupService,
    immich_asset_id: str,
    detection_id: int,
) -> None:
    """
    Shared 404 handling for the two detection-scoped write endpoints below:
    the asset must be scanned, and the detection must actually belong to it
    -- both checked through the same read-only `PhotoLookupService` every
    other Photo Lookup endpoint already uses, before any write is attempted.
    """
    lookup = lookup_service.get(immich_asset_id)

    if lookup is None:
        raise HTTPException(
            status_code=404,
            detail=f"No scanned photo found for Immich asset {immich_asset_id}",
        )

    if not any(
        detection.detection_id == detection_id for detection in lookup.detections
    ):
        raise HTTPException(
            status_code=404,
            detail=f"Detection {detection_id} not found on asset {immich_asset_id}",
        )


def _assignment_error(e: Exception) -> HTTPException:
    if isinstance(e, ImmichDownloadError):
        return HTTPException(
            status_code=502,
            detail=f"Failed to fetch photo from Immich: {e}",
        )

    status_code = 404 if "not found" in str(e).lower() else 400

    return HTTPException(status_code=status_code, detail=str(e))


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


@router.post(
    "/{immich_asset_id}/detections/{detection_id}/assign",
    response_model=DetectionAssignResponse,
)
def assign_detection(
    immich_asset_id: str,
    detection_id: int,
    request: DetectionAssignRequest,
    lookup_service: Annotated[PhotoLookupService, Depends(get_photo_lookup_service)],
    service: Annotated[
        ManualDetectionAssignmentService,
        Depends(get_manual_detection_assignment_service),
    ],
):
    # Issue #261: map a crop-less detection (YOLO labeled it outside
    # {dog, cat}, so the pipeline never created a crop for it) to a
    # species/identity a human names directly, without depending on an
    # automatic classifier run -- see ManualDetectionAssignmentService's
    # docstring for why.
    _require_detection_on_asset(lookup_service, immich_asset_id, detection_id)

    try:
        crop = service.assign(detection_id, request.species, request.identity)
    except (ValueError, ImmichDownloadError) as e:
        raise _assignment_error(e) from e

    return DetectionAssignResponse.from_crop(crop)


@router.post(
    "/{immich_asset_id}/detections/{detection_id}/not-animal",
    response_model=DetectionAssignResponse,
)
def mark_detection_not_animal(
    immich_asset_id: str,
    detection_id: int,
    lookup_service: Annotated[PhotoLookupService, Depends(get_photo_lookup_service)],
    service: Annotated[
        ManualDetectionAssignmentService,
        Depends(get_manual_detection_assignment_service),
    ],
):
    # Same crop-less case as assign_detection above, but confirming the
    # detector was right not to treat this box as a dog/cat (or declining to
    # name it) rather than mapping it to one.
    _require_detection_on_asset(lookup_service, immich_asset_id, detection_id)

    try:
        crop = service.mark_not_animal(detection_id)
    except (ValueError, ImmichDownloadError) as e:
        raise _assignment_error(e) from e

    return DetectionAssignResponse.from_crop(crop)
