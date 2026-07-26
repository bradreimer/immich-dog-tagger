from fastapi import FastAPI

from immich_dog_tagger.api.routes import (
    classifications,
    crops,
    dogs,
    health,
    review,
)


def create_app() -> FastAPI:
    app = FastAPI(
        title="Immich Dog Tagger API",
        version="0.3.0",
    )

    app.include_router(classifications.router)
    app.include_router(crops.router)
    app.include_router(dogs.router)
    app.include_router(health.router)
    app.include_router(review.router)

    return app


app = create_app()
