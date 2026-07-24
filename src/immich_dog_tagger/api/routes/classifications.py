from fastapi import APIRouter, Depends

from sqlalchemy.orm import Session

from immich_dog_tagger.api.dependencies import (
    get_correction_service,
    get_session,
)


router = APIRouter(
    prefix="/classifications",
)


@router.post("/{classification_id}/correct")
def correct(
    classification_id: int,
    identity: str,
    session: Session = Depends(get_session),
):
    service = get_correction_service(session)

    return service.correct(
        classification_id,
        identity,
    )
