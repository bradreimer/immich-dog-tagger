"""
Discards a detection's crop file without breaking a learned example that still uses it.

Re-detect (`detect --force`, per-photo Repair) and derived-data crop repair replace every
detection on a photo, and the new crops are written to the same `{asset}_{index}.jpg` names
(`CropWriter.write`). An `EmbeddingExample` pointing at one of those files would otherwise lose its
source image, or silently end up pointing at a different detection's crop (issue #380). A learned
example is a human decision about one specific image, so that image is moved to a name re-detect
never writes and the example follows it.
"""

from pathlib import Path
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from immich_dog_tagger.models import EmbeddingExample


def discard_crop_file(session: Session, crop_path: str) -> None:
    """
    Delete `crop_path`, unless a learned example uses it: then move it to a unique, example-owned
    name in the same directory and update those examples' `crop_path`. Doesn't commit -- the
    caller decides the transaction boundary.
    """
    path = Path(crop_path)

    examples = session.scalars(
        select(EmbeddingExample).where(EmbeddingExample.crop_path == crop_path)
    ).all()

    if not examples:
        path.unlink(missing_ok=True)
        return

    if not path.exists():
        # Nothing left to keep; derived-data repair handles the orphan (issue #379).
        return

    kept = path.with_name(f"{path.stem}_example_{uuid4().hex[:12]}{path.suffix}")
    path.replace(kept)

    for example in examples:
        example.crop_path = str(kept)
