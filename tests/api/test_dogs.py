from sqlalchemy import select
from sqlalchemy.orm import Session

from immich_dog_tagger.models import Crop, CropClassification, Identity


def test_dogs_list_is_empty_on_clean_install(api_client):
    response = api_client.get("/dogs")

    assert response.status_code == 200
    assert response.json() == []


def test_dogs_crud(api_client, engine):
    with Session(engine) as session:
        identity = Identity(name="Fibs")
        session.add(identity)
        session.commit()

        dog_id = identity.id

    response = api_client.get("/dogs")
    assert response.status_code == 200
    assert response.json() == [
        {
            "id": dog_id,
            "name": "Fibs",
            "species": "dog",
            "active": True,
        }
    ]

    response = api_client.post(
        "/dogs",
        json={
            "name": "Hermann",
        },
    )

    assert response.status_code == 200
    created = response.json()
    assert created["name"] == "Hermann"
    created_id = created["id"]

    response = api_client.put(
        f"/dogs/{created_id}",
        json={
            "name": "Hermann Prime",
        },
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Hermann Prime"

    response = api_client.delete(f"/dogs/{created_id}")

    assert response.status_code == 200
    assert response.json()["active"] is False

    response = api_client.post(f"/dogs/{created_id}/activate")

    assert response.status_code == 200
    assert response.json()["active"] is True


def test_dogs_reject_duplicate_and_reserved_names(api_client):
    first = api_client.post(
        "/dogs",
        json={
            "name": "Henri",
        },
    )

    assert first.status_code == 200

    duplicate = api_client.post(
        "/dogs",
        json={
            "name": "Henri",
        },
    )

    assert duplicate.status_code == 400

    reserved = api_client.post(
        "/dogs",
        json={
            "name": "Unknown",
        },
    )

    assert reserved.status_code == 400


def test_dogs_list_can_include_inactive(api_client):
    created = api_client.post(
        "/dogs",
        json={
            "name": "Cooper",
        },
    ).json()

    api_client.delete(f"/dogs/{created['id']}")

    active_only = api_client.get("/dogs", params={"include_inactive": False})
    assert active_only.status_code == 200
    assert active_only.json() == []

    all_dogs = api_client.get("/dogs")

    assert all_dogs.status_code == 200
    assert all_dogs.json()[0]["name"] == "Cooper"
    assert all_dogs.json()[0]["active"] is False


def test_dogs_merge_reassigns_and_reports_the_counts(api_client, engine):
    source = api_client.post("/dogs", json={"name": "Fibsy"}).json()
    target = api_client.post("/dogs", json={"name": "Fibs"}).json()

    with Session(engine) as session:
        crop = Crop(detection_id=1, path="fibsy-a.jpg")
        session.add(crop)
        session.flush()
        session.add(
            CropClassification(
                crop=crop,
                identity="Fibsy",
                confidence=0.95,
            )
        )
        session.commit()

    response = api_client.post(
        f"/dogs/{source['id']}/merge",
        json={"target_id": target["id"]},
    )

    assert response.status_code == 200

    payload = response.json()
    assert payload["source"]["name"] == "Fibsy"
    assert payload["source"]["active"] is False
    assert payload["target"]["name"] == "Fibs"
    assert payload["classifications_reassigned"] == 1

    with Session(engine) as session:
        classification = session.scalars(select(CropClassification)).one()
        assert classification.identity == "Fibs"


def test_dogs_merge_rejects_a_cross_species_merge(api_client):
    dog = api_client.post("/dogs", json={"name": "Max", "species": "dog"}).json()
    cat = api_client.post("/dogs", json={"name": "Max", "species": "cat"}).json()

    response = api_client.post(
        f"/dogs/{cat['id']}/merge",
        json={"target_id": dog["id"]},
    )

    assert response.status_code == 400
    assert "same species" in response.json()["detail"]


def test_dogs_merge_404s_for_an_unknown_identity(api_client):
    target = api_client.post("/dogs", json={"name": "Fibs"}).json()

    response = api_client.post(
        "/dogs/9999/merge",
        json={"target_id": target["id"]},
    )

    assert response.status_code == 404
