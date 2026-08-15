from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from immich_dog_tagger.enums import (
    ClassificationSources,
    EmbeddingSources,
    ReviewActions,
    Species,
)
from immich_dog_tagger.models import (
    Asset,
    Crop,
    CropClassification,
    Detection,
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
            crop_path="references/fibs/example.jpg",
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
        assert results[0].suggestion.example_path == Path("references/fibs/example.jpg")


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
            crop_path="references/hermann/example.jpg",
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


def test_review_queue_count_matches_active_review_result_count(engine):
    """DT-1102: review_queue_count() must count exactly what active_review()
    would return, so /metrics and /review can never silently drift apart."""
    with Session(engine) as session:
        unknown_crop = Crop(detection_id=1, path="unknown.jpg")
        low_crop = Crop(detection_id=2, path="low.jpg")
        good_crop = Crop(detection_id=3, path="good.jpg")
        reviewed_crop = Crop(detection_id=4, path="reviewed.jpg")

        session.add_all([unknown_crop, low_crop, good_crop, reviewed_crop])
        session.flush()

        reviewed_classification = CropClassification(
            crop=reviewed_crop, identity=None, confidence=-1.0
        )

        session.add_all(
            [
                CropClassification(crop=unknown_crop, identity=None, confidence=-1.0),
                CropClassification(crop=low_crop, identity="Hermann", confidence=0.60),
                CropClassification(crop=good_crop, identity="Fibs", confidence=0.95),
                reviewed_classification,
            ]
        )
        session.flush()

        session.add(
            ReviewAction(
                classification_id=reviewed_classification.id,
                action=ReviewActions.SKIP,
            )
        )
        session.commit()

        service = ReviewQueryService(session)

        assert service.review_queue_count() == len(service.active_review())
        assert service.review_queue_count() == 2


def test_review_query_includes_matched_example_path(engine):
    with Session(engine) as session:
        identity = Identity(name="Hermann")

        example = EmbeddingExample(
            identity=identity,
            crop_path="references/hermann/example.jpg",
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


def test_review_query_includes_photo_captured_at(engine):
    """DT-1111: ReviewItem.captured_at is the reviewed photo's own capture
    date (Crop -> Detection -> Asset), not the matched example's date."""
    captured_at = datetime(2019, 3, 3, 12, 0, 0, tzinfo=UTC)

    with Session(engine) as session:
        asset = Asset(
            immich_asset_id="asset-1",
            extension=".jpg",
            captured_at=captured_at,
        )

        detection = Detection(
            asset=asset,
            label="dog",
            confidence=0.99,
            x1=0,
            y1=0,
            x2=100,
            y2=100,
        )

        crop = Crop(
            detection=detection,
            path="crop.jpg",
        )

        classification = CropClassification(
            crop=crop,
            identity=None,
            confidence=0.5,
        )

        session.add(classification)
        session.commit()

        results = ReviewQueryService(session).classifications()

        assert len(results) == 1
        assert results[0].captured_at == captured_at.replace(tzinfo=None)


def test_review_query_captured_at_is_none_without_asset(engine):
    """A crop whose detection/asset chain is missing (orphaned rows, or test
    fixtures that don't bother with it) must yield captured_at=None rather
    than raising."""
    with Session(engine) as session:
        classification = create_test_classification(session)

        results = ReviewQueryService(session).classifications()

        assert len(results) == 1
        assert results[0].classification_id == classification.id
        assert results[0].captured_at is None


def test_review_returns_queue(api_client, engine):
    with Session(engine) as session:
        identity = Identity(
            name="Hermann",
        )

        example = EmbeddingExample(
            identity=identity,
            crop_path="references/hermann/example.jpg",
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
        "candidates": [],
    }

    assert item["suggestion"]["identity"] == "Hermann"
    assert item["suggestion"]["example_id"] == example_id
    assert item["suggestion"]["example_path"] == "references/hermann/example.jpg"


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


def test_review_queue_stats_remaining_matches_review_queue_count(engine):
    """Bug fix regression: review_queue_stats().remaining must equal
    review_queue_count() (what active_review() actually returns), not
    total - reviewed. A confidently-classified item with no review action
    is unreviewed but does not belong in "remaining"."""
    with Session(engine) as session:
        confident_crop = Crop(detection_id=1, path="confident.jpg")
        needs_review_crop = Crop(detection_id=1, path="needs-review.jpg")

        session.add_all([confident_crop, needs_review_crop])
        session.flush()

        session.add_all(
            [
                CropClassification(
                    crop=confident_crop,
                    identity="Fibs",
                    confidence=0.95,
                ),
                CropClassification(
                    crop=needs_review_crop,
                    identity=None,
                    confidence=0.5,
                ),
            ]
        )
        session.commit()

        service = ReviewQueryService(session)
        stats = service.review_queue_stats()

        assert stats.total == 2
        assert stats.reviewed == 0
        assert stats.remaining == 1
        assert stats.remaining == service.review_queue_count()
        assert stats.remaining == len(service.active_review())


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


def test_review_candidate_conflict_filter(api_client, engine):
    with Session(engine) as session:
        crop = Crop(
            detection_id=1,
            path="conflict.jpg",
        )

        session.add(crop)
        session.flush()

        classification = CropClassification(
            crop=crop,
            identity="Hermann",
            confidence=0.50,
            candidates=[
                {
                    "identity": "Fibs",
                    "similarity": 0.85,
                }
            ],
        )

        session.add(classification)
        session.commit()

        crop_id = crop.id

    response = api_client.get(
        "/review",
        params={
            "candidate_conflict": True,
        },
    )

    assert response.status_code == 200

    items = response.json()

    assert len(items) == 1
    assert items[0]["crop_id"] == crop_id


def test_review_query_sets_reason_for_unknown(engine):
    with Session(engine) as session:
        crop = Crop(
            detection_id=1,
            path="unknown.jpg",
        )

        classification = CropClassification(
            crop=crop,
            identity=None,
            confidence=0.9,
        )

        session.add(classification)
        session.commit()

        result = ReviewQueryService(session).active_review()

        assert result[0].reason == "unknown"


def test_review_query_reason_temporal_mismatch_takes_precedence_in_queue(engine):
    """v1.5/ADR-003: temporal-mismatch is checked before candidate-conflict,
    so an item with both gets the more specific, more actionable reason."""
    with Session(engine) as session:
        crop = Crop(detection_id=1, path="temporal-mismatch.jpg")
        session.add(crop)
        session.flush()

        classification = CropClassification(
            crop=crop,
            identity="Fibs",
            confidence=0.50,
            candidates=[
                {
                    "identity": "Fibs",
                    "similarity": 0.50,
                    "temporal_weight": 0.2,
                }
            ],
        )

        session.add(classification)
        session.commit()

        results = ReviewQueryService(session).active_review()

        assert len(results) == 1
        assert results[0].reason == "temporal-mismatch"


def test_review_query_reason_temporal_mismatch_surfaces_even_when_confident(engine):
    """A temporally weak match that would otherwise be confidently accepted
    -- and so never appear in the default review queue at all -- must still
    be labeled wherever it *is* shown (e.g. the library), rather than
    looking like an ordinary unflagged confident match."""
    with Session(engine) as session:
        crop = Crop(detection_id=1, path="confident-temporal-mismatch.jpg")
        session.add(crop)
        session.flush()

        classification = CropClassification(
            crop=crop,
            identity="Fibs",
            confidence=0.95,
            candidates=[
                {
                    "identity": "Fibs",
                    "similarity": 0.95,
                    "temporal_weight": 0.2,
                }
            ],
        )

        session.add(classification)
        session.commit()

        # Confident -> excluded from the default queue, same as today.
        assert ReviewQueryService(session).active_review() == []

        # But still labeled, e.g. for the library (DT-1112), which shows
        # every classification regardless of confidence.
        results = ReviewQueryService(session).classifications()

        assert len(results) == 1
        assert results[0].reason == "temporal-mismatch"


def test_review_query_active_review_reason_unknown(engine):
    with Session(engine) as session:
        crop = Crop(
            detection_id=1,
            path="unknown.jpg",
        )

        session.add(crop)
        session.flush()

        classification = CropClassification(
            crop=crop,
            identity=None,
            confidence=0.95,
        )

        session.add(classification)
        session.commit()

        results = ReviewQueryService(session).active_review()

        assert len(results) == 1
        assert results[0].reason == "unknown"


def test_review_query_active_review_reason_low_confidence(engine):
    with Session(engine) as session:
        crop = Crop(
            detection_id=1,
            path="low-confidence.jpg",
        )

        session.add(crop)
        session.flush()

        classification = CropClassification(
            crop=crop,
            identity="Hermann",
            confidence=0.50,
        )

        session.add(classification)
        session.commit()

        results = ReviewQueryService(session).active_review()

        assert len(results) == 1
        assert results[0].reason == "low-confidence"


def test_review_query_active_review_reason_candidate_conflict(engine):
    with Session(engine) as session:
        crop = Crop(
            detection_id=1,
            path="candidate-conflict.jpg",
        )

        session.add(crop)
        session.flush()

        classification = CropClassification(
            crop=crop,
            identity="Hermann",
            confidence=0.50,
            candidates=[
                {
                    "identity": "Fibs",
                    "similarity": 0.94,
                }
            ],
        )

        session.add(classification)
        session.commit()

        results = ReviewQueryService(session).active_review()

        assert len(results) == 1
        assert results[0].reason == "candidate-conflict"


def test_review_query_filters_candidate_conflict(engine):
    with Session(engine) as session:
        conflict_crop = Crop(
            detection_id=1,
            path="conflict.jpg",
        )

        normal_crop = Crop(
            detection_id=2,
            path="normal.jpg",
        )

        session.add_all(
            [
                conflict_crop,
                normal_crop,
            ]
        )
        session.flush()

        session.add_all(
            [
                CropClassification(
                    crop=conflict_crop,
                    identity="Hermann",
                    confidence=0.50,
                    candidates=[
                        {
                            "identity": "Fibs",
                            "similarity": 0.9,
                        }
                    ],
                ),
                CropClassification(
                    crop=normal_crop,
                    identity="Fibs",
                    confidence=0.95,
                    candidates=[],
                ),
            ]
        )

        session.commit()

        results = ReviewQueryService(session).active_review(
            candidate_conflict=True,
        )

        assert len(results) == 1
        assert results[0].path.name == "conflict.jpg"


def test_library_includes_reviewed_and_unreviewed_items(engine):
    """DT-1112: unlike active_review(), library() must not exclude items
    that already have a review action -- that's the entire point."""
    with Session(engine) as session:
        reviewed_crop = Crop(detection_id=1, path="reviewed.jpg")
        unreviewed_crop = Crop(detection_id=1, path="unreviewed.jpg")

        session.add_all([reviewed_crop, unreviewed_crop])
        session.flush()

        reviewed = CropClassification(
            crop=reviewed_crop,
            identity="Fibs",
            confidence=0.95,
        )
        unreviewed = CropClassification(
            crop=unreviewed_crop,
            identity="Hermann",
            confidence=0.60,
        )

        session.add_all([reviewed, unreviewed])
        session.flush()

        session.add(
            ReviewAction(
                classification_id=reviewed.id,
                action=ReviewActions.CORRECT,
                identity="Fibs",
            )
        )
        session.commit()

        page = ReviewQueryService(session).library()

        assert page.total == 2
        assert len(page.items) == 2

        by_path = {entry.item.filename: entry for entry in page.items}

        assert by_path["reviewed.jpg"].reviewed is True
        assert by_path["reviewed.jpg"].reviewed_at is not None
        assert by_path["unreviewed.jpg"].reviewed is False
        assert by_path["unreviewed.jpg"].reviewed_at is None


def test_library_filters_by_identity(engine):
    with Session(engine) as session:
        fibs_crop = Crop(detection_id=1, path="fibs.jpg")
        hermann_crop = Crop(detection_id=1, path="hermann.jpg")

        session.add_all([fibs_crop, hermann_crop])
        session.flush()

        session.add_all(
            [
                CropClassification(crop=fibs_crop, identity="Fibs", confidence=0.9),
                CropClassification(
                    crop=hermann_crop, identity="Hermann", confidence=0.9
                ),
            ]
        )
        session.commit()

        page = ReviewQueryService(session).library(identity="Fibs")

        assert page.total == 1
        assert page.items[0].item.filename == "fibs.jpg"


def test_library_filters_by_species(engine):
    with Session(engine) as session:
        dog_crop = Crop(detection_id=1, path="dog.jpg", species=Species.DOG)
        cat_crop = Crop(detection_id=1, path="cat.jpg", species=Species.CAT)

        session.add_all([dog_crop, cat_crop])
        session.flush()

        session.add_all(
            [
                CropClassification(crop=dog_crop, identity="Fibs", confidence=0.9),
                CropClassification(crop=cat_crop, identity="Whiskers", confidence=0.9),
            ]
        )
        session.commit()

        page = ReviewQueryService(session).library(species="cat")

        assert page.total == 1
        assert page.items[0].item.filename == "cat.jpg"


def test_library_filters_by_reviewed(engine):
    with Session(engine) as session:
        reviewed_crop = Crop(detection_id=1, path="reviewed.jpg")
        unreviewed_crop = Crop(detection_id=1, path="unreviewed.jpg")

        session.add_all([reviewed_crop, unreviewed_crop])
        session.flush()

        reviewed = CropClassification(
            crop=reviewed_crop,
            identity="Fibs",
            confidence=0.95,
        )
        unreviewed = CropClassification(
            crop=unreviewed_crop,
            identity="Hermann",
            confidence=0.60,
        )

        session.add_all([reviewed, unreviewed])
        session.flush()

        session.add(
            ReviewAction(
                classification_id=reviewed.id,
                action=ReviewActions.CORRECT,
                identity="Fibs",
            )
        )
        session.commit()

        reviewed_page = ReviewQueryService(session).library(reviewed=True)
        unreviewed_page = ReviewQueryService(session).library(reviewed=False)

        assert reviewed_page.total == 1
        assert reviewed_page.items[0].item.filename == "reviewed.jpg"

        assert unreviewed_page.total == 1
        assert unreviewed_page.items[0].item.filename == "unreviewed.jpg"


def test_library_filters_by_captured_date_range(engine):
    with Session(engine) as session:
        old_asset = Asset(
            immich_asset_id="old",
            extension=".jpg",
            captured_at=datetime(2015, 1, 1, tzinfo=UTC),
        )
        old_detection = Detection(
            asset=old_asset, label="dog", confidence=0.9, x1=0, y1=0, x2=1, y2=1
        )
        old_crop = Crop(detection=old_detection, path="old.jpg")

        new_asset = Asset(
            immich_asset_id="new",
            extension=".jpg",
            captured_at=datetime(2023, 1, 1, tzinfo=UTC),
        )
        new_detection = Detection(
            asset=new_asset, label="dog", confidence=0.9, x1=0, y1=0, x2=1, y2=1
        )
        new_crop = Crop(detection=new_detection, path="new.jpg")

        session.add_all([old_crop, new_crop])
        session.flush()

        session.add_all(
            [
                CropClassification(crop=old_crop, identity="Fibs", confidence=0.9),
                CropClassification(crop=new_crop, identity="Fibs", confidence=0.9),
            ]
        )
        session.commit()

        after_page = ReviewQueryService(session).library(
            captured_after=datetime(2020, 1, 1, tzinfo=UTC)
        )
        before_page = ReviewQueryService(session).library(
            captured_before=datetime(2020, 1, 1, tzinfo=UTC)
        )

        assert after_page.total == 1
        assert after_page.items[0].item.filename == "new.jpg"

        assert before_page.total == 1
        assert before_page.items[0].item.filename == "old.jpg"


def test_library_pagination(engine):
    with Session(engine) as session:
        for i in range(5):
            crop = Crop(detection_id=1, path=f"dog-{i}.jpg")
            session.add(crop)
            session.flush()
            session.add(CropClassification(crop=crop, identity="Fibs", confidence=0.9))
        session.commit()

        first_page = ReviewQueryService(session).library(limit=2, offset=0)
        second_page = ReviewQueryService(session).library(limit=2, offset=2)

        assert first_page.total == 5
        assert len(first_page.items) == 2
        assert second_page.total == 5
        assert len(second_page.items) == 2

        first_ids = {entry.item.classification_id for entry in first_page.items}
        second_ids = {entry.item.classification_id for entry in second_page.items}

        assert first_ids.isdisjoint(second_ids)
