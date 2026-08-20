"""
API for rescuing photos the detector missed (issue #147).
"""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from immich_dog_tagger.enums import AssetStatus, Species
from immich_dog_tagger.models import Asset, Identity


def _seed(session: Session, *, immich_asset_id="missed-1") -> int:
    session.add(Identity(name="Fibs", species=Species.DOG, is_active=True))

    asset = Asset(
        immich_asset_id=immich_asset_id,
        extension=".jpg",
        status=AssetStatus.DETECTED,
        captured_at=datetime(2026, 1, 1, tzinfo=UTC).replace(tzinfo=None),
    )

    session.add(asset)
    session.commit()

    return asset.id


def test_undetected_endpoint_lists_photos_with_no_crop(api_client, engine):
    with Session(engine) as session:
        asset_id = _seed(session)

    response = api_client.get("/undetected")

    assert response.status_code == 200

    payload = response.json()

    assert payload["total"] == 1
    assert payload["items"][0]["asset_id"] == asset_id
    assert payload["items"][0]["immich_asset_id"] == "missed-1"
    assert payload["items"][0]["identities"] == []


def test_tag_endpoint_records_the_pet(api_client, engine):
    with Session(engine) as session:
        asset_id = _seed(session)

    response = api_client.post(
        f"/undetected/{asset_id}/tags",
        json={"identity": "Fibs", "species": "dog"},
    )

    assert response.status_code == 200
    assert response.json()["identities"] == ["Fibs"]

    listed = api_client.get("/undetected").json()
    assert listed["items"][0]["identities"] == ["Fibs"]


def test_tag_endpoint_is_idempotent(api_client, engine):
    with Session(engine) as session:
        asset_id = _seed(session)

    for _ in range(2):
        response = api_client.post(
            f"/undetected/{asset_id}/tags",
            json={"identity": "Fibs", "species": "dog"},
        )

    assert response.json()["identities"] == ["Fibs"]


def test_tag_endpoint_400s_for_an_unknown_pet(api_client, engine):
    with Session(engine) as session:
        asset_id = _seed(session)

    response = api_client.post(
        f"/undetected/{asset_id}/tags",
        json={"identity": "Nobody", "species": "dog"},
    )

    assert response.status_code == 400


def test_tag_endpoint_400s_for_an_unknown_asset(api_client, engine):
    with Session(engine) as session:
        _seed(session)

    response = api_client.post(
        "/undetected/9999/tags",
        json={"identity": "Fibs", "species": "dog"},
    )

    assert response.status_code == 400


def test_untag_endpoint_removes_the_tag(api_client, engine):
    with Session(engine) as session:
        asset_id = _seed(session)

    api_client.post(
        f"/undetected/{asset_id}/tags",
        json={"identity": "Fibs", "species": "dog"},
    )

    response = api_client.request(
        "DELETE",
        f"/undetected/{asset_id}/tags",
        json={"identity": "Fibs", "species": "dog"},
    )

    assert response.status_code == 200
    assert response.json()["identities"] == []


def test_untag_endpoint_404s_for_a_tag_that_does_not_exist(api_client, engine):
    with Session(engine) as session:
        asset_id = _seed(session)

    response = api_client.request(
        "DELETE",
        f"/undetected/{asset_id}/tags",
        json={"identity": "Fibs", "species": "dog"},
    )

    assert response.status_code == 404


def test_undetected_endpoint_filters_by_tagged_state(api_client, engine):
    with Session(engine) as session:
        asset_id = _seed(session)

        session.add(
            Asset(
                immich_asset_id="missed-2",
                extension=".jpg",
                status=AssetStatus.DETECTED,
            )
        )
        session.commit()

    api_client.post(
        f"/undetected/{asset_id}/tags",
        json={"identity": "Fibs", "species": "dog"},
    )

    untagged = api_client.get("/undetected?tagged=false").json()
    assert [item["immich_asset_id"] for item in untagged["items"]] == ["missed-2"]

    tagged = api_client.get("/undetected?tagged=true").json()
    assert [item["immich_asset_id"] for item in tagged["items"]] == ["missed-1"]
