from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from immich_dog_tagger.api.dependencies import get_session
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
    session: Annotated[Session, Depends(get_session)],
):
    service = ReviewQueryService(session)

    items = service.classifications(
        identity=identity,
    )

    return [
        ClassificationResponse(
            classification_id=item.classification_id,
            crop_id=item.crop_id,
            identity=item.identity,
            confidence=item.confidence,
            filename=item.filename,
        )
        for item in items
    ]
