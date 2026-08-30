"""
Issue #179: the photo-lookup endpoints backing "paste an Immich link, see
what this instance tagged in that photo".
"""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from immich_dog_tagger.api.dependencies import get_immich_client
from immich_dog_tagger.enums import Species
from immich_dog_tagger.immich import ImmichDownloadError
from immich_dog_tagger.models import Asset, Crop, CropClassification, Detection


class FakeImmichClient:
    def __init__(
        self, content: bytes = b"fake-jpeg-bytes", error: Exception | None = None
    ):
        self.content = content
        self.error = error
        self.requested_asset_ids: list[str] = []

    def download_asset(self, asset_id: str) -> bytes:
        self.requested_asset_ids.append(asset_id)

        if self.error is not None:
            raise self.error

        return self.content


def _seed_asset_with_detection(session: Session, *, immich_asset_id="asset-1"):
    asset = Asset(
        immich_asset_id=immich_asset_id,
        extension=".jpg",
        captured_at=datetime(2020, 6, 1, tzinfo=UTC),
    )

    detection = Detection(
        asset=asset,
        label="dog",
        confidence=0.9,
        x1=10,
        y1=20,
        x2=110,
        y2=220,
    )

    crop = Crop(
        detection=detection,
        path="crop.jpg",
        species=Species.DOG,
    )

    classification = CropClassification(
        crop=crop,
        identity="Fibs",
        confidence=0.87,
    )

    session.add(classification)
    session.commit()

    return asset.id


def test_photo_lookup_404_for_unscanned_asset(api_client):
    response = api_client.get("/photo-lookup/does-not-exist")

    assert response.status_code == 404


def test_photo_lookup_returns_detections(api_client, engine):
    with Session(engine) as session:
        _seed_asset_with_detection(session)

    response = api_client.get("/photo-lookup/asset-1")

    assert response.status_code == 200

    payload = response.json()

    assert payload["immich_asset_id"] == "asset-1"
    assert len(payload["detections"]) == 1

    detection = payload["detections"][0]
    assert (detection["x1"], detection["y1"], detection["x2"], detection["y2"]) == (
        10,
        20,
        110,
        220,
    )
    assert detection["identity"] == "Fibs"
    assert detection["confidence"] == 0.87
    assert detection["not_animal"] is False


def test_photo_lookup_image_404_for_unscanned_asset(api_client):
    response = api_client.get("/photo-lookup/does-not-exist/image")

    assert response.status_code == 404


def test_photo_lookup_image_proxies_bytes_from_immich(api_client, engine):
    with Session(engine) as session:
        _seed_asset_with_detection(session)

    fake_client = FakeImmichClient(content=b"the-original-photo-bytes")
    api_client.app.dependency_overrides[get_immich_client] = lambda: fake_client

    response = api_client.get("/photo-lookup/asset-1/image")

    assert response.status_code == 200
    assert response.content == b"the-original-photo-bytes"
    assert response.headers["content-type"] == "image/jpeg"
    assert fake_client.requested_asset_ids == ["asset-1"]


def test_photo_lookup_image_502_when_immich_fetch_fails(api_client, engine):
    with Session(engine) as session:
        _seed_asset_with_detection(session)

    fake_client = FakeImmichClient(error=ImmichDownloadError("boom"))
    api_client.app.dependency_overrides[get_immich_client] = lambda: fake_client

    response = api_client.get("/photo-lookup/asset-1/image")

    assert response.status_code == 502
