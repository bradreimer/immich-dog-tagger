from fastapi import APIRouter, Request

from immich_dog_tagger.services.scheduler_loop import SchedulerHealth

router = APIRouter()


@router.get("/health")
def health(request: Request):
    scheduler_health: SchedulerHealth | None = getattr(
        request.app.state, "scheduler_health", None
    )
    return {
        "status": "ok",
        "scheduler": scheduler_health.as_dict() if scheduler_health else None,
    }
