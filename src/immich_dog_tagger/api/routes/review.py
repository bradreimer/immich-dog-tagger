from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from immich_dog_tagger.api.dependencies import (
    get_review_action_service,
    get_review_query_service,
    get_session,
)
from immich_dog_tagger.api.schemas import (
    ReviewItemResponse,
    ReviewQueueStatsResponse,
)
from immich_dog_tagger.services.review_actions import ReviewActionService

router = APIRouter(
    prefix="/review",
)


@router.get(
    "",
    response_model=list[ReviewItemResponse],
)
def review(
    session: Annotated[Session, Depends(get_session)],
    threshold: float = Query(0.80),
    limit: int = Query(50),
    unknown: bool = Query(False),
    confidence_below: float | None = Query(None),
    candidate_conflict: bool = Query(False),
):
    service = get_review_query_service(session)

    items = service.active_review(
        threshold=threshold,
        limit=limit,
        unknown=unknown,
        confidence_below=confidence_below,
        candidate_conflict=candidate_conflict,
    )

    return [ReviewItemResponse.from_item(item) for item in items]


@router.get(
    "/stats",
    response_model=ReviewQueueStatsResponse,
)
def review_stats(
    session: Annotated[Session, Depends(get_session)],
):
    service = get_review_query_service(session)

    stats = service.review_queue_stats()

    return ReviewQueueStatsResponse(
        total=stats.total,
        reviewed=stats.reviewed,
        remaining=stats.remaining,
    )


@router.post("/{classification_id}/skip")
def skip_review(
    classification_id: int,
    service: Annotated[ReviewActionService, Depends(get_review_action_service)],
):
    try:
        service.skip(
            classification_id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=404,
            detail=str(e),
        ) from e

    return {
        "status": "skipped",
    }
