from sqlalchemy.orm import Session, joinedload

from .models import CropClassification


def get_crop_classifications(session: Session):
    return (
        session.query(CropClassification)
        .options(joinedload(CropClassification.crop))
        .order_by(CropClassification.id)
        .all()
    )
