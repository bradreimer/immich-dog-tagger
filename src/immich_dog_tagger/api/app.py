import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from immich_dog_tagger.api.routes import (
    classifications,
    crops,
    dogs,
    embedding_examples,
    health,
    jobs,
    review,
    schedules,
)
from immich_dog_tagger.config import load_config
from immich_dog_tagger.services.scheduler_loop import SchedulerHealth, run_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    from immich_dog_tagger.api.dependencies import get_engine

    config = load_config()
    engine = get_engine()
    scheduler_health = SchedulerHealth()
    stop_event = threading.Event()
    thread = threading.Thread(
        target=run_scheduler,
        args=(engine, config, scheduler_health, stop_event),
        daemon=True,
        name="immich-dog-tagger-scheduler",
    )
    thread.start()
    app.state.scheduler_health = scheduler_health
    yield
    stop_event.set()
    thread.join(timeout=10)


def create_app() -> FastAPI:
    app = FastAPI(
        title="Immich Dog Tagger API",
        version="0.3.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
        ],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(classifications.router)
    app.include_router(crops.router)
    app.include_router(dogs.router)
    app.include_router(embedding_examples.router)
    app.include_router(health.router)
    app.include_router(jobs.router)
    app.include_router(review.router)
    app.include_router(schedules.router)

    return app


app = create_app()
