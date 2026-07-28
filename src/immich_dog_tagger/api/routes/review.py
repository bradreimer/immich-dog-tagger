from fastapi import APIRouter, Depends, Query

from sqlalchemy.orm import Session

from immich_dog_tagger.api.dependencies import (
    get_review_query_service,
    get_session,
)
from immich_dog_tagger.api.schemas import ReviewItemResponse, ReviewQueueStatsResponse


router = APIRouter(
    prefix="/review",
)


@router.get(
    "",
    response_model=list[ReviewItemResponse],
)
def review(
    threshold: float = Query(0.80),
    limit: int = Query(50),
    session: Session = Depends(get_session),
):
    service = get_review_query_service(session)

    items = service.active_review(
        threshold=threshold,
        limit=limit,
    )

    return [ReviewItemResponse.from_item(item) for item in items]


@router.get(
    "/stats",
    response_model=ReviewQueueStatsResponse,
)
def review_stats(
    session: Session = Depends(get_session),
):
    service = get_review_query_service(session)

    stats = service.review_queue_stats()

    return ReviewQueueStatsResponse(
        total=stats.total,
        reviewed=stats.reviewed,
        remaining=stats.remaining,
    )
