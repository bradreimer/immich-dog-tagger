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


def test_library_returns_reviewed_and_unreviewed(api_client, engine):
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

    response = api_client.get("/library")

    assert response.status_code == 200

    payload = response.json()

    assert payload["total"] == 2
    assert payload["limit"] == 50
    assert payload["offset"] == 0
    assert len(payload["items"]) == 2

    reviewed_flags = {entry["reviewed"] for entry in payload["items"]}
    assert reviewed_flags == {True, False}


def test_library_filters_by_query_params(api_client, engine):
    with Session(engine) as session:
        asset = Asset(
            immich_asset_id="asset-1",
            extension=".jpg",
            captured_at=datetime(2019, 3, 3, tzinfo=UTC),
        )
        detection = Detection(
            asset=asset, label="dog", confidence=0.9, x1=0, y1=0, x2=1, y2=1
        )
        crop = Crop(detection=detection, path="fibs.jpg")

        session.add(crop)
        session.flush()

        session.add(CropClassification(crop=crop, identity="Fibs", confidence=0.9))
        session.commit()

    response = api_client.get(
        "/library",
        params={
            "identity": "Fibs",
            "species": "dog",
            "reviewed": "false",
            "captured_after": "2019-01-01T00:00:00",
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["total"] == 1
    assert payload["items"][0]["item"]["captured_at"] == "2019-03-03T00:00:00"


def test_library_pagination_params(api_client, engine):
    with Session(engine) as session:
        for i in range(5):
            crop = Crop(detection_id=1, path=f"dog-{i}.jpg")
            session.add(crop)
            session.flush()
            session.add(CropClassification(crop=crop, identity="Fibs", confidence=0.9))
        session.commit()

    response = api_client.get("/library", params={"limit": 2, "offset": 2})

    assert response.status_code == 200

    payload = response.json()

    assert payload["total"] == 5
    assert payload["limit"] == 2
    assert payload["offset"] == 2
    assert len(payload["items"]) == 2


def test_review_queue_unaffected_by_library_route(api_client, engine):
    """DT-1112 acceptance criterion: the existing GET /review queue endpoint
    is unchanged in behavior by the addition of GET /library."""
    with Session(engine) as session:
        reviewed_crop = Crop(detection_id=1, path="reviewed.jpg")

        session.add(reviewed_crop)
        session.flush()

        reviewed = CropClassification(
            crop=reviewed_crop,
            identity="Fibs",
            confidence=0.95,
        )

        session.add(reviewed)
        session.flush()

        session.add(
            ReviewAction(
                classification_id=reviewed.id,
                action=ReviewActions.CORRECT,
                identity="Fibs",
            )
        )
        session.commit()

    review_response = api_client.get("/review")
    library_response = api_client.get("/library")

    assert review_response.status_code == 200
    assert library_response.status_code == 200

    # The reviewed item must still be excluded from the queue...
    assert review_response.json() == []

    # ...but present in the library.
    assert library_response.json()["total"] == 1
