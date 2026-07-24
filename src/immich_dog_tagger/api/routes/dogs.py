from fastapi import APIRouter, Depends

from sqlalchemy.orm import Session

from immich_dog_tagger.api.dependencies import (
    get_session,
)
from immich_dog_tagger.services.review_query import (
    ReviewQueryService,
)


router = APIRouter(
    prefix="/dogs",
)


@router.get("/{identity}")
def dog(
    identity: str,
    session: Session = Depends(get_session),
):
    service = ReviewQueryService(session)

    return service.classifications(
        identity=identity,
    )
