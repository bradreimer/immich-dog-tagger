from fastapi import APIRouter, Depends

from immich_dog_tagger.api.dependencies import get_correction_service
from immich_dog_tagger.api.schemas import CorrectionRequest
from immich_dog_tagger.services.correction import ClassificationCorrectionService


router = APIRouter(
    prefix="/classifications",
)


@router.post("/{classification_id}/correct")
def correct(
    classification_id: int,
    request: CorrectionRequest,
    service: ClassificationCorrectionService = Depends(get_correction_service),
):
    return service.correct(
        classification_id,
        request.identity,
    )
