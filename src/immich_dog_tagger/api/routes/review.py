from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from immich_dog_tagger.api.dependencies import (
    get_review_action_service,
    get_review_grouping_service,
    get_review_query_service,
    get_session,
)
from immich_dog_tagger.api.schemas import (
    ReviewGroupsProposalResponse,
    ReviewItemResponse,
    ReviewQueueStatsResponse,
)
from immich_dog_tagger.enums import ClusterSort
from immich_dog_tagger.services.review_actions import ReviewActionService
from immich_dog_tagger.services.review_groups import ReviewGroupingService

router = APIRouter(
    prefix="/review",
)


@router.get(
    "",
    response_model=list[ReviewItemResponse],
)
def review(
    session: Annotated[Session, Depends(get_session)],
    # None (not a hardcoded default) so an explicit ?threshold= still
    # overrides, but leaving it off -- as every real caller does -- falls
    # through to active_review()'s own default: the owner's actual
    # tagging_sensitivity policy, not a threshold baked in at import time
    # (#321/#322).
    threshold: float | None = Query(None),
    limit: int = Query(50),
    unknown: bool = Query(False),
    confidence_below: float | None = Query(None),
    candidate_conflict: bool = Query(False),
    species: str | None = Query(None),
    identity: str | None = Query(None),
    captured_after: datetime | None = Query(None),
    captured_before: datetime | None = Query(None),
):
    service = get_review_query_service(session)

    items = service.active_review(
        threshold=threshold,
        limit=limit,
        unknown=unknown,
        confidence_below=confidence_below,
        candidate_conflict=candidate_conflict,
        species=species,
        identity=identity,
        captured_after=captured_after,
        captured_before=captured_before,
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


@router.get(
    "/groups",
    response_model=ReviewGroupsProposalResponse,
)
def review_groups(
    service: Annotated[
        ReviewGroupingService,
        Depends(get_review_grouping_service),
    ],
    sort: ClusterSort = Query(ClusterSort.CONFIDENCE_DESC),
):
    """
    Grouped mode (see docs/specs/review-tab-batch-approval.md): the active
    review queue's pending items, clustered into visually-similar batches
    across every identity with pending work -- not one pet selected up
    front. A read: it writes nothing, and proposes groupings only.
    """
    proposal = service.groups(sort=sort)

    return ReviewGroupsProposalResponse.from_proposal(proposal)


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
