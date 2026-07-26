from sqlalchemy.orm import Session

from immich_dog_tagger.models import Crop, CropClassification


def test_correct_classification(api_client, engine):
    with Session(engine) as session:
        crop = Crop(
            detection_id=1,
            path="hermann.jpg",
        )

        classification = CropClassification(
            crop=crop,
            identity=None,
            confidence=0.4,
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


def test_correct_classification_not_found(api_client):
    response = api_client.post(
        "/classifications/999999/correct",
        json={
            "identity": "Hermann",
        },
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Classification 999999 not found",
    }
