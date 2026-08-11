from sqlalchemy.orm import Session

from immich_dog_tagger.models import Crop, CropClassification


def test_metrics_empty_project(api_client):
    response = api_client.get("/metrics")

    assert response.status_code == 200

    payload = response.json()
    assert payload["eligible_count"] == 0
    assert payload["coverage"] is None
    assert payload["review_rate"] is None
    assert payload["last_reclassification"] is None
    assert payload["pass_history"] == []


def test_metrics_reflects_classification_counts(api_client, engine):
    with Session(engine) as session:
        crop = Crop(detection_id=1, path="dog.jpg")
        session.add(crop)
        session.flush()

        session.add(
            CropClassification(
                crop=crop,
                identity="Hermann",
                confidence=0.95,
            )
        )
        session.commit()

    response = api_client.get("/metrics")

    assert response.status_code == 200
    payload = response.json()
    assert payload["eligible_count"] == 1
    assert payload["confident_count"] == 1
    assert payload["coverage"] == 1.0
