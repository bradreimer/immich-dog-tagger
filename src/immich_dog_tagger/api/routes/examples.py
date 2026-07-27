from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path

router = APIRouter(
    prefix="/examples",
)


@router.get("/{path:path}")
def example(path: str):
    image = Path(path)

    if not image.exists():
        raise HTTPException(
            status_code=404,
            detail="Example not found",
        )

    return FileResponse(
        image,
        media_type="image/jpeg",
    )
