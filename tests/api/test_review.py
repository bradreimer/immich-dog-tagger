from sqlalchemy.orm import Session

from immich_dog_tagger.models import Crop, CropClassification


def test_review_queue(api_client):
    response = api_client.get(
        "/review",
        params={
            "limit": 5,
        },
    )

    assert response.status_code == 200
    assert isinstance(response.json(), list)


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
    assert item["image_url"] == f"/crops/{crop.id}"

    assert "path" not in item
    assert "/some/internal/storage/path" not in response.text
