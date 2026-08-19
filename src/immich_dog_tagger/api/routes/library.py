from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from immich_dog_tagger.api.dependencies import (
    get_cluster_approval_service,
    get_cluster_service,
    get_review_query_service,
    get_session,
)
from immich_dog_tagger.api.schemas import (
    ClusterApprovalRequest,
    ClusterApprovalResponse,
    ClusterProposalResponse,
    LibraryPageResponse,
)
from immich_dog_tagger.enums import Species
from immich_dog_tagger.services.clusters import (
    ClusterApprovalService,
    RecommendationClusterService,
)

router = APIRouter(
    prefix="/library",
)


@router.get(
    "",
    response_model=LibraryPageResponse,
)
def library(
    session: Annotated[Session, Depends(get_session)],
    identity: str | None = Query(None),
    species: str | None = Query(None),
    reviewed: bool | None = Query(None),
    captured_after: datetime | None = Query(None),
    captured_before: datetime | None = Query(None),
    limit: int = Query(50),
    offset: int = Query(0),
):
    service = get_review_query_service(session)

    page = service.library(
        identity=identity,
        species=species,
        reviewed=reviewed,
        captured_after=captured_after,
        captured_before=captured_before,
        limit=limit,
        offset=offset,
    )

    return LibraryPageResponse.from_page(page)


@router.get(
    "/clusters",
    response_model=ClusterProposalResponse,
)
def library_clusters(
    service: Annotated[
        RecommendationClusterService,
        Depends(get_cluster_service),
    ],
    identity: str = Query(...),
    species: Species = Query(...),
):
    """
    The pending recommendations for one pet, grouped into clusters of
    visually similar crops. A read: it writes nothing and proposes
    groupings only -- no identity is settled until a human approves.
    """
    try:
        proposal = service.clusters(
            identity=identity,
            species=species,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=404,
            detail=str(e),
        ) from e

    return ClusterProposalResponse.from_proposal(proposal)


@router.post(
    "/clusters/approve",
    response_model=ClusterApprovalResponse,
)
def approve_cluster(
    request: ClusterApprovalRequest,
    service: Annotated[
        ClusterApprovalService,
        Depends(get_cluster_approval_service),
    ],
):
    """
    Assign the pet's identity to every listed member, as N ordinary
    corrections. Album membership reconciles on the next operator-triggered
    sync (ADR-006), not here.
    """
    try:
        summary = service.approve(
            identity=request.identity,
            species=request.species,
            classification_ids=request.classification_ids,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e),
        ) from e

    return ClusterApprovalResponse.from_summary(summary)
