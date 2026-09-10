from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from immich_dog_tagger.api.dependencies import get_engine
from immich_dog_tagger.models import EmbeddingExample

router = APIRouter(
    prefix="/embedding-examples",
)


@router.get(
    "/{example_id}/image",
)
def embedding_example_image(
    example_id: int,
    engine: Annotated[Engine, Depends(get_engine)],
):
    # Looks the path up through its own short-lived session rather than a
    # request-scoped `Depends(get_session)` (issue #277): FastAPI only runs
    # a `yield` dependency's cleanup after the full response has been sent,
    # so a session threaded through as a normal dependency would stay
    # checked out of the pool for as long as the image takes to stream
    # back, not just for this lookup -- see crops.py's `crop` route/
    # `get_viewable_crop_path` for the full story.
    with Session(engine) as session:
        example = session.get(
            EmbeddingExample,
            example_id,
        )

        if example is None:
            raise HTTPException(
                status_code=404,
                detail="Embedding example not found",
            )

        path = example.crop_path

    return FileResponse(
        path,
        media_type="image/jpeg",
    )
