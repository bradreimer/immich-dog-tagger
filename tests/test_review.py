from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from immich_dog_tagger.enums import (
    ClassificationSources,
    EmbeddingSources,
    ReviewActions,
)
from immich_dog_tagger.models import (
    Crop,
    CropClassification,
    EmbeddingExample,
    Identity,
    ReviewAction,
)
from immich_dog_tagger.services.review_query import ReviewQueryService
from tests.conftest import create_test_classification


class FakeLearner:
    def __init__(self):
        self.calls = []

    def learn_image(
        self,
        identity,
        image_path,
        source,
        captured_at=None,
    ):
        self.calls.append(
            {
                "identity": identity,
                "image_path": image_path,
                "source": source,
                "captured_at": captured_at,
            }
        )

        return True


def test_review_query_service_classifications(engine):
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

        results = ReviewQueryService(session).classifications()

        assert len(results) == 1
        assert results[0].prediction.identity == "Fibs"
        assert results[0].crop_id == crop.id
        assert results[0].classification_id == classification.id
        assert results[0].path == Path("test.jpg")
        assert results[0].filename == "test.jpg"

        assert results[0].suggestion.example_path == Path("training/fibs/example.jpg")


def test_review_query_filters_by_identity(engine):
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

        results = ReviewQueryService(session).classifications(
            identity="Fibs",
        )

        assert len(results) == 1
        assert results[0].prediction.identity == "Fibs"
        assert results[0].path.name == "fibs.jpg"


def test_review_query_filters_unknown(engine):
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

        results = ReviewQueryService(session).classifications(
            unknown=True,
        )

        assert len(results) == 1
        assert results[0].prediction.identity is None
        assert results[0].path.name == "unknown.jpg"


def test_review_query_orders_by_lowest_confidence_first(engine):
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

        results = ReviewQueryService(session).classifications()

        assert results[0].prediction.similarity == 0.70
        assert results[1].prediction.similarity == 0.99


def test_review_query_summary(engine):
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

        summary = ReviewQueryService(session).summary()

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


def test_review_query_summary_empty(engine):
    with Session(engine) as session:
        summary = ReviewQueryService(session).summary()

        assert summary.total == 0
        assert summary.identities == {}
        assert summary.unknown == 0
        assert summary.confidence_buckets == {
            "<0.80": 0,
            "0.80-0.90": 0,
            ">0.90": 0,
        }


def test_review_query_filters_low_confidence(engine):
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

        results = ReviewQueryService(session).classifications(
            confidence_below=0.80,
        )

        assert len(results) == 1
        assert results[0].prediction.identity == "Hermann"
        assert results[0].prediction.similarity == 0.70


def test_review_query_active_review_includes_unknown_and_low_confidence(engine):
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

        results = ReviewQueryService(session).active_review(
            threshold=0.80,
        )

        assert len(results) == 2

        assert {item.path.name for item in results} == {
            "unknown.jpg",
            "low.jpg",
        }

        low_result = next(item for item in results if item.path.name == "low.jpg")

        assert low_result.suggestion is not None
        assert low_result.suggestion.example_id == example.id


def test_review_query_includes_matched_example_path(engine):
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

        results = ReviewQueryService(session).classifications()

        assert len(results) == 1
        assert results[0].suggestion.example_id == example.id


def test_review_returns_queue(api_client, engine):
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

        crop = Crop(
            detection_id=1,
            path="fib.jpg",
        )

        classification = CropClassification(
            crop=crop,
            identity=None,
            confidence=-1.0,
            matched_example=example,
            source=ClassificationSources.AUTO,
        )

        session.add_all(
            [
                identity,
                example,
                classification,
            ]
        )

        session.commit()

        crop_id = crop.id
        example_id = example.id

    response = api_client.get(
        "/review",
    )

    assert response.status_code == 200

    items = response.json()

    assert len(items) == 1

    item = items[0]

    assert item["crop_id"] == crop_id

    assert item["prediction"] == {
        "identity": None,
        "similarity": -1.0,
    }

    assert item["suggestion"]["identity"] == "Hermann"
    assert item["suggestion"]["example_id"] == example_id


def test_review_query_active_review_excludes_skipped(engine):
    with Session(engine) as session:
        crop = Crop(
            detection_id=1,
            path="skipped.jpg",
        )

        session.add(crop)
        session.flush()

        classification = CropClassification(
            crop=crop,
            identity=None,
            confidence=0.50,
        )

        session.add(classification)
        session.flush()

        session.add(
            ReviewAction(
                classification_id=classification.id,
                action=ReviewActions.SKIP,
            )
        )

        session.commit()

        results = ReviewQueryService(session).active_review()

        assert len(results) == 0


def test_review_query_active_review_excludes_corrected(engine):
    with Session(engine) as session:
        classification = create_test_classification(session)

        session.add(
            ReviewAction(
                classification_id=classification.id,
                action=ReviewActions.CORRECT,
                identity="Hermann",
            )
        )

        session.commit()

        results = ReviewQueryService(session).active_review()

        assert classification.id not in [item.classification_id for item in results]


def test_review_query_stats_counts_review_actions(engine):
    with Session(engine) as session:
        skipped = create_test_classification(session)

        corrected = create_test_classification(session)

        session.add_all(
            [
                ReviewAction(
                    classification_id=skipped.id,
                    action=ReviewActions.SKIP,
                ),
                ReviewAction(
                    classification_id=corrected.id,
                    action=ReviewActions.CORRECT,
                    identity="Hermann",
                ),
            ]
        )

        session.commit()

        stats = ReviewQueryService(session).review_queue_stats()

        assert stats.total == 2
        assert stats.reviewed == 2
        assert stats.remaining == 0


def test_skip_review_endpoint(api_client, engine):
    with Session(engine) as session:
        crop = Crop(
            detection_id=1,
            path="skip.jpg",
        )

        session.add(crop)
        session.flush()

        classification = CropClassification(
            crop=crop,
            identity=None,
            confidence=0.50,
        )

        session.add(classification)
        session.commit()

        classification_id = classification.id

    response = api_client.post(
        f"/review/{classification_id}/skip",
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "skipped",
    }

    response = api_client.get("/review")

    assert response.status_code == 200
    assert response.json() == []


def test_skip_review(api_client, session):
    classification = create_test_classification(session)

    response = api_client.post(
        f"/review/{classification.id}/skip",
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "skipped"

    action = session.scalar(
        select(ReviewAction).where(
            ReviewAction.classification_id == classification.id,
            ReviewAction.action == ReviewActions.SKIP,
        )
    )

    assert action is not None


def test_skip_review_is_idempotent(api_client, session):
    classification = create_test_classification(session)

    response1 = api_client.post(
        f"/review/{classification.id}/skip",
    )

    response2 = api_client.post(
        f"/review/{classification.id}/skip",
    )

    assert response1.status_code == 200
    assert response2.status_code == 200

    actions = session.scalars(
        select(ReviewAction).where(
            ReviewAction.classification_id == classification.id,
            ReviewAction.action == ReviewActions.SKIP,
        )
    ).all()

    assert len(actions) == 1


def test_skip_review_missing_classification(api_client):
    response = api_client.post(
        "/review/99999/skip",
    )

    assert response.status_code == 404


def test_review_unknown_filter(api_client, engine):
    with Session(engine) as session:
        unknown_crop = Crop(
            detection_id=1,
            path="unknown.jpg",
        )

        known_crop = Crop(
            detection_id=1,
            path="known.jpg",
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
                    confidence=0.4,
                ),
                CropClassification(
                    crop=known_crop,
                    identity="Hermann",
                    confidence=1.0,
                ),
            ]
        )

        session.commit()

        unknown_crop_id = unknown_crop.id

    response = api_client.get(
        "/review",
        params={
            "unknown": True,
        },
    )

    assert response.status_code == 200

    items = response.json()

    assert len(items) == 1
    assert items[0]["crop_id"] == unknown_crop_id


def test_review_confidence_filter(api_client, engine):
    with Session(engine) as session:
        low_crop = Crop(
            detection_id=1,
            path="low.jpg",
        )

        high_crop = Crop(
            detection_id=1,
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
                    identity=None,
                    confidence=0.2,
                ),
                CropClassification(
                    crop=high_crop,
                    identity=None,
                    confidence=0.9,
                ),
            ]
        )

        session.commit()

        low_crop_id = low_crop.id

    response = api_client.get(
        "/review",
        params={
            "confidence_below": 0.5,
        },
    )

    assert response.status_code == 200

    items = response.json()

    assert len(items) == 1
    assert items[0]["crop_id"] == low_crop_id
