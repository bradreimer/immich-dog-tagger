from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Detection


def count_detections(
    session: Session,
    label: str | None = None,
) -> int:

    query = select(Detection)

    if label:
        query = query.where(Detection.label == label)

    return len(session.scalars(query).all())
