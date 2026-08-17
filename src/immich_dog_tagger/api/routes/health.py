from fastapi import APIRouter, Request

from immich_dog_tagger.services.scheduler_loop import SchedulerHealth
from immich_dog_tagger.version import get_version

router = APIRouter()


@router.get("/health")
def health(request: Request):
    scheduler_health: SchedulerHealth | None = getattr(
        request.app.state, "scheduler_health", None
    )
    return {
        "status": "ok",
        "version": get_version(),
        "scheduler": scheduler_health.as_dict() if scheduler_health else None,
    }
