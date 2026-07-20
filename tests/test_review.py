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


def test_review_filters_by_identity(engine):
    with Session(engine) as session:
        fibs_crop = Crop(
            detection_id=1,
            path="fibs.jpg",
        )

        hermann_crop = Crop(
            detection_id=2,
            path="hermann.jpg",
        )

        session.add_all(
            [
                fibs_crop,
                hermann_crop,
            ]
        )
        session.flush()

        session.add_all(
            [
                CropClassification(
                    crop=fibs_crop,
                    identity="Fibs",
                    confidence=0.95,
                ),
                CropClassification(
                    crop=hermann_crop,
                    identity="Hermann",
                    confidence=0.90,
                ),
            ]
        )

        session.commit()

        results = ReviewService(session).classifications(
            identity="Fibs",
        )

        assert len(results) == 1
        assert results[0].identity == "Fibs"
        assert results[0].path.name == "fibs.jpg"


def test_review_filters_unknown(engine):
    with Session(engine) as session:
        unknown_crop = Crop(
            detection_id=1,
            path="unknown.jpg",
        )

        known_crop = Crop(
            detection_id=2,
            path="fibs.jpg",
        )

        session.add_all(
            [
                unknown_crop,
                known_crop,
            ]
        )
        session.flush()

        session.add_all(
            [
                CropClassification(
                    crop=unknown_crop,
                    identity=None,
                    confidence=0.60,
                ),
                CropClassification(
                    crop=known_crop,
                    identity="Fibs",
                    confidence=0.95,
                ),
            ]
        )

        session.commit()

        results = ReviewService(session).classifications(
            unknown=True,
        )

        assert len(results) == 1
        assert results[0].identity is None
        assert results[0].path.name == "unknown.jpg"


def test_review_orders_by_lowest_confidence_first(engine):
    with Session(engine) as session:
        low_crop = Crop(
            detection_id=1,
            path="low.jpg",
        )

        high_crop = Crop(
            detection_id=2,
            path="high.jpg",
        )

        session.add_all(
            [
                low_crop,
                high_crop,
            ]
        )
        session.flush()

        session.add_all(
            [
                CropClassification(
                    crop=low_crop,
                    identity="Fibs",
                    confidence=0.70,
                ),
                CropClassification(
                    crop=high_crop,
                    identity="Fibs",
                    confidence=0.99,
                ),
            ]
        )

        session.commit()

        results = ReviewService(session).classifications()

        assert results[0].confidence == 0.70
        assert results[1].confidence == 0.99


def test_review_summary(engine):
    with Session(engine) as session:
        fibs_crop_1 = Crop(
            detection_id=1,
            path="fibs1.jpg",
        )

        fibs_crop_2 = Crop(
            detection_id=2,
            path="fibs2.jpg",
        )

        henri_crop = Crop(
            detection_id=3,
            path="henri.jpg",
        )

        unknown_crop = Crop(
            detection_id=4,
            path="unknown.jpg",
        )

        session.add_all(
            [
                fibs_crop_1,
                fibs_crop_2,
                henri_crop,
                unknown_crop,
            ]
        )
        session.flush()

        session.add_all(
            [
                CropClassification(
                    crop=fibs_crop_1,
                    identity="Fibs",
                    confidence=0.95,
                ),
                CropClassification(
                    crop=fibs_crop_2,
                    identity="Fibs",
                    confidence=0.85,
                ),
                CropClassification(
                    crop=henri_crop,
                    identity="Henri",
                    confidence=0.70,
                ),
                CropClassification(
                    crop=unknown_crop,
                    identity=None,
                    confidence=0.60,
                ),
            ]
        )

        session.commit()

        summary = ReviewService(session).summary()

        assert summary.total == 4

        assert summary.identities == {
            "Fibs": 2,
            "Henri": 1,
        }

        assert summary.unknown == 1

        assert summary.confidence_buckets == {
            "<0.80": 2,
            "0.80-0.90": 1,
            ">0.90": 1,
        }
