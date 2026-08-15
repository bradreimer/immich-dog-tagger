from datetime import UTC, datetime

from sqlalchemy.orm import Session

from immich_dog_tagger.enums import ClassificationSources, Species
from immich_dog_tagger.models import (
    Asset,
    Crop,
    CropClassification,
    Detection,
    Identity,
)
from immich_dog_tagger.services.pet_occurrences import PetOccurrenceService


def _seed_occurrence(engine, *, identity_name: str) -> int:
    with Session(engine) as session:
        identity = Identity(name=identity_name, species=Species.DOG)
        session.add(identity)
        session.commit()

        asset = Asset(
            immich_asset_id="a1",
            extension=".jpg",
            captured_at=datetime(2023, 1, 1, tzinfo=UTC),
            city="Seattle",
            country="United States",
            people=[{"id": "p1", "name": "Brad"}],
        )
        session.add(asset)
        session.flush()

        detection = Detection(
            asset_id=asset.id, label="dog", confidence=0.9, x1=0, y1=0, x2=1, y2=1
        )
        session.add(detection)
        session.flush()

        crop = Crop(detection_id=detection.id, path="a1.jpg", species=Species.DOG)
        session.add(crop)
        session.flush()

        classification = CropClassification(
            crop=crop,
            identity=identity_name,
            confidence=0.9,
            source=ClassificationSources.AUTO,
        )
        session.add(classification)
        session.commit()

        PetOccurrenceService(session).sync_classification(classification)
        session.commit()

        return identity.id


def test_insights_summary_404_for_unknown_dog(api_client):
    response = api_client.get("/dogs/999/insights/summary")

    assert response.status_code == 404


def test_insights_endpoints_return_derived_data(api_client, engine):
    identity_id = _seed_occurrence(engine, identity_name="Hermann")

    summary = api_client.get(f"/dogs/{identity_id}/insights/summary")
    assert summary.status_code == 200
    body = summary.json()
    assert body["identity_name"] == "Hermann"
    assert body["total_photos"] == 1
    assert body["top_place"]["city"] == "Seattle"
    assert body["top_person"]["person_id"] == "p1"

    places = api_client.get(f"/dogs/{identity_id}/insights/places")
    assert places.status_code == 200
    assert places.json()[0]["city"] == "Seattle"

    people = api_client.get(f"/dogs/{identity_id}/insights/people")
    assert people.status_code == 200
    assert people.json()[0]["person_id"] == "p1"

    timeline = api_client.get(f"/dogs/{identity_id}/insights/timeline")
    assert timeline.status_code == 200
    assert timeline.json()[0]["immich_asset_id"] == "a1"


def test_insights_summary_zero_state_for_dog_with_no_photos(api_client):
    created = api_client.post("/dogs", json={"name": "Cooper"}).json()

    response = api_client.get(f"/dogs/{created['id']}/insights/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["total_photos"] == 0
    assert body["top_place"] is None
    assert body["top_person"] is None
