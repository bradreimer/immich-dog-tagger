from sqlalchemy.orm import Session

from immich_dog_tagger.enums import ReviewActions
from immich_dog_tagger.models import Crop, CropClassification, ReviewAction


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

    assert data["remaining"] == (data["total"] - data["reviewed"])


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
        f"/review/{classification_id}/correct",
        json={
            "identity": "Hermann",
        },
    )

    assert response.status_code == 200

    response = api_client.get("/review")

    assert response.status_code == 200
    assert response.json() == []
