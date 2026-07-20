from pathlib import Path
from sqlalchemy.orm import Session
from immich_dog_tagger.models import Crop, CropClassification
from immich_dog_tagger.services.review import ReviewService


def test_review_classifications(engine):
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

        results = ReviewService(session).classifications()

        assert len(results) == 1
        assert results[0].identity == "Fibs"
        assert results[0].crop_id == crop.id
        assert results[0].classification_id == classification.id
        assert results[0].path == Path("test.jpg")
        assert results[0].filename == "test.jpg"
