from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from immich_dog_tagger.api.dependencies import (
    get_correction_service,
    get_review_query_service,
)
from immich_dog_tagger.api.schemas import (
    ClassificationResponse,
    CorrectionRequest,
    ReviewItemResponse,
    SpeciesCorrectionRequest,
)
from immich_dog_tagger.services.correction import ClassificationCorrectionService
from immich_dog_tagger.services.review_query import ReviewQueryService

router = APIRouter(
    prefix="/classifications",
)


@router.post("/{classification_id}/correct", response_model=ClassificationResponse)
def correct(
    classification_id: int,
    request: CorrectionRequest,
    service: Annotated[
        ClassificationCorrectionService,
        Depends(get_correction_service),
    ],
):
    try:
        classification = service.correct(
            classification_id,
            request.identity,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=404,
            detail=str(e),
        ) from e

    return ClassificationResponse(
        classification_id=classification.id,
        crop_id=classification.crop_id,
        identity=classification.identity,
        confidence=classification.confidence,
        filename=Path(classification.crop.path).name,
    )


@router.post("/{classification_id}/species", response_model=ReviewItemResponse)
def correct_species(
    classification_id: int,
    request: SpeciesCorrectionRequest,
    correction_service: Annotated[
        ClassificationCorrectionService,
        Depends(get_correction_service),
    ],
    review_query_service: Annotated[
        ReviewQueryService,
        Depends(get_review_query_service),
    ],
):
    try:
        correction_service.correct_species(
            classification_id,
            request.species,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=404,
            detail=str(e),
        ) from e

    item = review_query_service.item_for_classification(classification_id)

    if item is None:
        raise HTTPException(
            status_code=404,
            detail=f"Classification {classification_id} not found",
        )

    return ReviewItemResponse.from_item(item)
