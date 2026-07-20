from pathlib import Path
from sqlalchemy.orm import Session

from immich_dog_tagger.models import Crop, CropClassification
from immich_dog_tagger.services.review import ReviewService


def test_review_service_classifications(engine):
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


def test_review_classifications_order_by_confidence(engine):
    with Session(engine) as session:
        crop1 = Crop(detection_id=1, path="low.jpg")
        crop2 = Crop(detection_id=2, path="high.jpg")

        session.add_all([crop1, crop2])
        session.flush()

        session.add_all(
            [
                CropClassification(
                    crop=crop1,
                    identity="Fibs",
                    confidence=0.2,
                ),
                CropClassification(
                    crop=crop2,
                    identity="Fibs",
                    confidence=0.9,
                ),
            ]
        )

        session.commit()

        results = ReviewService(session).classifications()

        assert results[0].path.name == "low.jpg"
        assert results[1].path.name == "high.jpg"


def test_review_classifications_filter_identity(engine):
    with Session(engine) as session:
        crop1 = Crop(detection_id=1, path="dog.jpg")
        crop2 = Crop(detection_id=2, path="cat.jpg")

        session.add_all([crop1, crop2])
        session.flush()

        session.add_all(
            [
                CropClassification(
                    crop=crop1,
                    identity="Dog",
                    confidence=0.8,
                ),
                CropClassification(
                    crop=crop2,
                    identity="Cat",
                    confidence=0.9,
                ),
            ]
        )

        session.commit()

        results = ReviewService(session).classifications(identity="Dog")

        assert len(results) == 1
        assert results[0].identity == "Dog"
        assert results[0].path.name == "dog.jpg"
