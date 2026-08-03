from sqlalchemy.orm import Session

from immich_dog_tagger.models import Crop, CropClassification


def test_dogs_returns_classification_predictions(api_client, engine):
    with Session(engine) as session:
        crop = Crop(
            detection_id=1,
            path="fibs.jpg",
        )

        classification = CropClassification(
            crop=crop,
            identity="Fibs",
            confidence=0.93,
        )

        session.add(classification)
        session.commit()

        classification_id = classification.id
        crop_id = crop.id

    response = api_client.get("/dogs/Fibs")

    assert response.status_code == 200

    items = response.json()

    assert len(items) == 1
    assert items[0]["classification_id"] == classification_id
    assert items[0]["crop_id"] == crop_id
    assert items[0]["identity"] == "Fibs"
    assert items[0]["confidence"] == 0.93
    assert items[0]["filename"] == "fibs.jpg"
