from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from immich_dog_tagger.api.dependencies import get_session
from immich_dog_tagger.models import EmbeddingExample

router = APIRouter(
    prefix="/embedding-examples",
)


@router.get(
    "/{example_id}/image",
)
def embedding_example_image(
    example_id: int,
    session: Annotated[Session, Depends(get_session)],
):
    example = session.get(
        EmbeddingExample,
        example_id,
    )

    if example is None:
        raise HTTPException(
            status_code=404,
            detail="Embedding example not found",
        )

    return FileResponse(
        example.crop_path,
        media_type="image/jpeg",
    )
