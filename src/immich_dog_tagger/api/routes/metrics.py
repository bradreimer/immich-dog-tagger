from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from immich_dog_tagger.api.dependencies import get_session
from immich_dog_tagger.api.schemas import LearningMetricsResponse
from immich_dog_tagger.services.metrics import MetricsService

router = APIRouter(
    prefix="/metrics",
)


@router.get(
    "",
    response_model=LearningMetricsResponse,
)
def learning_metrics(
    session: Annotated[Session, Depends(get_session)],
):
    service = MetricsService(session)

    return LearningMetricsResponse.from_metrics(service.learning_metrics())
