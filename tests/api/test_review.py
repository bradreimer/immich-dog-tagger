from datetime import UTC, datetime

from sqlalchemy.orm import Session

from immich_dog_tagger.enums import ReviewActions
from immich_dog_tagger.models import (
    Asset,
    Crop,
    CropClassification,
    Detection,
    ReviewAction,
)


def test_review_queue(api_client):
    response = api_client.get(
        "/review",
        params={
            "limit": 5,
        },
    )

    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_review_item_returns_reason(api_client, engine):
    with Session(engine) as session:
        crop = Crop(
            detection_id=1,
            path="unknown.jpg",
        )

        classification = CropClassification(
            crop=crop,
            identity=None,
            confidence=0.5,
        )

        session.add(classification)
        session.commit()

    response = api_client.get("/review")

    assert response.status_code == 200

    item = response.json()[0]

    assert item["reason"] == "unknown"


def test_review_stats(api_client):
    response = api_client.get("/review/stats")

    assert response.status_code == 200

    data = response.json()

    assert data["total"] >= 0
    assert data["reviewed"] >= 0
    assert data["remaining"] >= 0


def test_review_stats_remaining_excludes_confidently_classified_items(
    api_client, engine
):
    """Regression test: `remaining` must match what GET /review actually
    returns, not `total - reviewed`. A confidently-classified, unreviewed
    item is not part of either -- it was the DT-1106 Mission Control
    banner/sidebar badge bug (both driven by this field) claiming "N images
    need review" while the /review queue itself showed nothing."""
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

    stats_response = api_client.get("/review/stats")
    review_response = api_client.get("/review")

    assert stats_response.status_code == 200
    assert review_response.status_code == 200

    stats = stats_response.json()
    queue = review_response.json()

    assert stats["total"] == 2
    assert stats["reviewed"] == 0
    # Not 2 (total - reviewed) -- only the unknown item actually needs a
    # human, matching len(queue) exactly.
    assert stats["remaining"] == 1
    assert stats["remaining"] == len(queue)


def test_review_item_returns_image_url(api_client, engine):
    with Session(engine) as session:
        crop = Crop(
            detection_id=1,
            path="/some/internal/storage/path/fibs.jpg",
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

        crop_id = crop.id
        classification_id = classification.id

    response = api_client.get("/review")

    assert response.status_code == 200

    items = response.json()

    assert len(items) == 1

    item = items[0]

    assert item["classification_id"] == classification_id
    assert item["crop_id"] == crop_id
    assert item["reason"] == "unknown"
    assert item["image_url"] == f"/crops/{crop.id}"

    assert "path" not in item
    assert "/some/internal/storage/path" not in response.text


def test_review_item_returns_captured_at(api_client, engine):
    """DT-1111: GET /review items include the reviewed photo's own capture
    date."""
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
            path="fibs.jpg",
        )

        classification = CropClassification(
            crop=crop,
            identity=None,
            confidence=0.5,
        )

        session.add(classification)
        session.commit()

    response = api_client.get("/review")

    assert response.status_code == 200

    item = response.json()[0]

    assert item["captured_at"] == "2019-03-03T12:00:00"


def test_review_item_captured_at_is_null_without_asset(api_client, engine):
    with Session(engine) as session:
        crop = Crop(
            detection_id=1,
            path="unknown.jpg",
        )

        classification = CropClassification(
            crop=crop,
            identity=None,
            confidence=0.5,
        )

        session.add(classification)
        session.commit()

    response = api_client.get("/review")

    assert response.status_code == 200

    item = response.json()[0]

    assert item["captured_at"] is None


def test_review_item_returns_immich_asset_id(api_client, engine):
    """#128: GET /review items carry the Immich asset id so the review card
    can link to the original photo."""
    with Session(engine) as session:
        asset = Asset(
            immich_asset_id="asset-42",
            extension=".jpg",
            captured_at=datetime(2019, 3, 3, 12, 0, 0, tzinfo=UTC),
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
            path="fibs.jpg",
        )

        classification = CropClassification(
            crop=crop,
            identity=None,
            confidence=0.5,
        )

        session.add(classification)
        session.commit()

    response = api_client.get("/review")

    assert response.status_code == 200

    item = response.json()[0]

    assert item["immich_asset_id"] == "asset-42"


def test_review_item_immich_asset_id_is_null_without_asset(api_client, engine):
    with Session(engine) as session:
        crop = Crop(
            detection_id=1,
            path="unknown.jpg",
        )

        classification = CropClassification(
            crop=crop,
            identity=None,
            confidence=0.5,
        )

        session.add(classification)
        session.commit()

    response = api_client.get("/review")

    assert response.status_code == 200

    item = response.json()[0]

    assert item["immich_asset_id"] is None


def test_review_queue_interleaves_both_species(api_client, engine):
    # DT-1110 acceptance criterion 4: dog and cat items share one queue,
    # sorted by the existing priority rules -- no species grouping/filter.
    with Session(engine) as session:
        dog_crop = Crop(detection_id=1, path="dog.jpg", species="dog")
        cat_crop = Crop(detection_id=1, path="cat.jpg", species="cat")

        session.add(CropClassification(crop=dog_crop, identity=None, confidence=0.5))
        session.add(CropClassification(crop=cat_crop, identity=None, confidence=0.5))
        session.commit()

    response = api_client.get("/review")

    assert response.status_code == 200

    items = response.json()

    assert len(items) == 2
    assert {item["species"] for item in items} == {"dog", "cat"}


def test_review_skip_creates_single_action(api_client, engine):
    with Session(engine) as session:
        crop = Crop(
            detection_id=1,
            path="to-skip.jpg",
        )

        classification = CropClassification(
            crop=crop,
            identity=None,
            confidence=0.45,
        )

        session.add(classification)
        session.commit()

        classification_id = classification.id

    first = api_client.post(f"/review/{classification_id}/skip")
    second = api_client.post(f"/review/{classification_id}/skip")

    assert first.status_code == 200
    assert second.status_code == 200

    with Session(engine) as session:
        actions = (
            session.query(ReviewAction)
            .filter(
                ReviewAction.classification_id == classification_id,
                ReviewAction.action == ReviewActions.SKIP,
            )
            .all()
        )

        assert len(actions) == 1


def test_review_skip_not_found(api_client):
    response = api_client.post("/review/999999/skip")

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Classification 999999 not found",
    }


def test_correct_review_removes_item_from_queue(api_client, engine):
    with Session(engine) as session:
        crop = Crop(
            detection_id=1,
            path="correct.jpg",
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
        f"/classifications/{classification_id}/correct",
        json={
            "identity": "Hermann",
        },
    )

    assert response.status_code == 200

    response = api_client.get("/review")

    assert response.status_code == 200
    assert response.json() == []


def test_review_correct_endpoint_removed(api_client):
    response = api_client.post(
        "/review/1/correct",
        json={
            "identity": "Hermann",
        },
    )

    assert response.status_code == 404
