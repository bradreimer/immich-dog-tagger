from fastapi import APIRouter, Depends, Query

from sqlalchemy.orm import Session

from immich_dog_tagger.api.dependencies import (
    get_review_query_service,
    get_session,
)
from immich_dog_tagger.api.schemas import (
    ReviewItemResponse,
)


router = APIRouter(
    prefix="/review",
)


@router.get(
    "/pending",
    response_model=list[ReviewItemResponse],
)
def pending(
    threshold: float = Query(0.80),
    limit: int | None = Query(None),
    session: Session = Depends(get_session),
):
    service = get_review_query_service(session)

    items = service.active_review(
        threshold=threshold,
        limit=limit,
    )

    return [ReviewItemResponse.from_item(item) for item in items]
