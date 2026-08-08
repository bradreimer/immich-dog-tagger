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
)


def create_app() -> FastAPI:
    app = FastAPI(
        title="Immich Dog Tagger API",
        version="0.3.0",
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

    return app


app = create_app()
