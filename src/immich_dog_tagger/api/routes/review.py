from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from immich_dog_tagger.api.dependencies import (
    get_review_query_service,
    get_session,
)
from immich_dog_tagger.api.schemas import ReviewItemResponse, ReviewQueueStatsResponse
from immich_dog_tagger.enums import ReviewActions
from immich_dog_tagger.models import CropClassification, ReviewAction


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


@router.post("/{classification_id}/skip")
def skip_review(
    classification_id: int,
    session: Session = Depends(get_session),
):
    classification = session.get(
        CropClassification,
        classification_id,
    )

    if classification is None:
        raise HTTPException(
            status_code=404,
            detail="Classification not found",
        )

    existing_skip = session.scalar(
        select(ReviewAction).where(
            ReviewAction.classification_id == classification.id,
            ReviewAction.action == ReviewActions.SKIP,
        )
    )

    if existing_skip is None:
        session.add(
            ReviewAction(
                classification_id=classification.id,
                action=ReviewActions.SKIP,
            )
        )

    session.commit()

    return {
        "status": "skipped",
    }
