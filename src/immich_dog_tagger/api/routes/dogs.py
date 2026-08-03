from typing import Annotated

from fastapi import APIRouter, Depends

from immich_dog_tagger.api.dependencies import get_review_query_service
from immich_dog_tagger.api.schemas import ClassificationResponse
from immich_dog_tagger.services.review_query import ReviewQueryService

router = APIRouter(
    prefix="/dogs",
)


@router.get(
    "/{identity}",
    response_model=list[ClassificationResponse],
)
def dog(
    identity: str,
    service: Annotated[ReviewQueryService, Depends(get_review_query_service)],
):
    items = service.classifications(
        identity=identity,
    )

    return [
        ClassificationResponse(
            classification_id=item.classification_id,
            crop_id=item.crop_id,
            identity=item.prediction.identity,
            confidence=item.prediction.similarity,
            filename=item.filename,
        )
        for item in items
    ]
