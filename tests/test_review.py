from pathlib import Path
from sqlalchemy.orm import Session

from immich_dog_tagger.models import (
    ClassificationSources,
    Crop,
    CropClassification,
    EmbeddingExample,
    EmbeddingSources,
    Identity,
)
from immich_dog_tagger.services.review import ReviewService


def test_review_service_classifications(engine):
    with Session(engine) as session:
        crop = Crop(
            detection_id=1,
            path="test.jpg",
        )

        session.add(crop)
        session.flush()

        identity = Identity(name="Fibs")
        example = EmbeddingExample(
            identity=identity,
            crop_path="training/fibs/example.jpg",
            embedding=b"123",
            source=EmbeddingSources.REVIEW,
        )

        classification = CropClassification(
            crop=crop,
            identity="Fibs",
            confidence=0.95,
            matched_example=example,
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

        assert results[0].matched_example_path == Path("training/fibs/example.jpg")


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


def test_review_summary_empty(engine):
    with Session(engine) as session:
        summary = ReviewService(session).summary()

        assert summary.total == 0
        assert summary.identities == {}
        assert summary.unknown == 0
        assert summary.confidence_buckets == {
            "<0.80": 0,
            "0.80-0.90": 0,
            ">0.90": 0,
        }


def test_review_filters_low_confidence(engine):
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
                    identity="Hermann",
                    confidence=0.70,
                ),
                CropClassification(
                    crop=high_crop,
                    identity="Fibs",
                    confidence=0.95,
                ),
            ]
        )

        session.commit()

        results = ReviewService(session).classifications(
            confidence_below=0.80,
        )

        assert len(results) == 1
        assert results[0].identity == "Hermann"
        assert results[0].confidence == 0.70


def test_review_active_review_includes_unknown_and_low_confidence(engine):
    with Session(engine) as session:
        identity = Identity(
            name="Hermann",
        )

        example = EmbeddingExample(
            identity=identity,
            crop_path="training/hermann/example.jpg",
            embedding=b"fake",
            source=EmbeddingSources.REVIEW,
        )

        unknown_crop = Crop(
            detection_id=1,
            path="unknown.jpg",
        )

        low_crop = Crop(
            detection_id=2,
            path="low.jpg",
        )

        good_crop = Crop(
            detection_id=3,
            path="good.jpg",
        )

        session.add_all(
            [
                identity,
                example,
                unknown_crop,
                low_crop,
                good_crop,
            ]
        )
        session.flush()

        session.add_all(
            [
                CropClassification(
                    crop=unknown_crop,
                    identity=None,
                    confidence=0.95,
                ),
                CropClassification(
                    crop=low_crop,
                    identity="Hermann",
                    confidence=0.60,
                    matched_example=example,
                ),
                CropClassification(
                    crop=good_crop,
                    identity="Fibs",
                    confidence=0.95,
                ),
            ]
        )

        session.commit()

        results = ReviewService(session).active_review(
            threshold=0.80,
        )

        assert len(results) == 2

        assert {item.path.name for item in results} == {
            "unknown.jpg",
            "low.jpg",
        }

        low_result = next(item for item in results if item.path.name == "low.jpg")

        assert low_result.matched_example_path == Path("training/hermann/example.jpg")


def test_review_includes_matched_example_path(engine):
    with Session(engine) as session:
        identity = Identity(name="Hermann")

        example = EmbeddingExample(
            identity=identity,
            crop_path="training/hermann/example.jpg",
            embedding=b"fake",
            source=EmbeddingSources.REVIEW,
        )

        crop = Crop(
            detection_id=1,
            path="crop.jpg",
        )

        session.add_all(
            [
                identity,
                example,
                crop,
            ]
        )

        session.flush()

        classification = CropClassification(
            crop=crop,
            identity="Hermann",
            confidence=0.75,
            matched_example=example,
        )

        session.add(classification)
        session.commit()

        results = ReviewService(session).classifications()

        assert len(results) == 1
        assert results[0].matched_example_path == Path("training/hermann/example.jpg")


def test_apply_review_marks_classification_as_review(engine):
    with Session(engine) as session:
        crop = Crop(
            detection_id=1,
            path="test.jpg",
        )

        classification = CropClassification(
            crop=crop,
            identity=None,
            confidence=0.4,
        )

        session.add(classification)
        session.commit()

        service = ReviewService(session)

        service.apply_review(
            classification.id,
            "Hermann",
        )

        session.commit()

        result = session.get(
            CropClassification,
            classification.id,
        )

        assert result.identity == "Hermann"
        assert result.source == ClassificationSources.REVIEW


def test_apply_review_rejects_unknown_classification(engine):
    with Session(engine) as session:
        service = ReviewService(session)

        try:
            service.apply_review(
                999,
                "Hermann",
            )
        except ValueError as exc:
            assert str(exc) == "Classification 999 not found"
        else:
            raise AssertionError("Expected ValueError")
