from sqlalchemy.orm import Session

from immich_dog_tagger.models import (
    Crop,
    CropClassification,
)
from immich_dog_tagger.repository import (
    get_crop_classifications,
)


def test_get_crop_classifications(engine):
    with Session(engine) as session:
        crop = Crop(
            detection_id=1,
            path="test.jpg",
        )

        session.add(crop)
        session.flush()

        classification = CropClassification(
            crop=crop,
            identity="Fibs",
            confidence=0.95,
        )

        session.add(classification)
        session.commit()

        results = get_crop_classifications(session)

        assert len(results) == 1
        assert results[0].identity == "Fibs"
        assert results[0].crop.path == "test.jpg"
