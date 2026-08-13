from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from immich_dog_tagger.api.dependencies import (
    get_review_query_service,
    get_session,
)
from immich_dog_tagger.api.schemas import LibraryPageResponse

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
