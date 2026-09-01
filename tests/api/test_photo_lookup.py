"""
Issue #179: the photo-lookup endpoints backing "paste an Immich link, see
what this instance tagged in that photo".
"""

import io
from datetime import UTC, datetime
from pathlib import Path

from PIL import Image
from sqlalchemy.orm import Session

from immich_dog_tagger.api.dependencies import get_immich_client
from immich_dog_tagger.enums import Species
from immich_dog_tagger.immich import ImmichDownloadError
from immich_dog_tagger.models import Asset, Crop, CropClassification, Detection

_HEIC_FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"

# EXIF tag 274 is Orientation.
_ORIENTATION_TAG = 274


def _jpeg_bytes(image: Image.Image, orientation: int | None = None) -> bytes:
    exif = image.getexif()

    if orientation is not None:
        exif[_ORIENTATION_TAG] = orientation

    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", exif=exif)

    return buffer.getvalue()


class FakeImmichClient:
    def __init__(self, content: bytes | None = None, error: Exception | None = None):
        self.content = (
            content
            if content is not None
            else _jpeg_bytes(Image.new("RGB", (200, 100), "white"))
        )
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


def test_photo_lookup_reflects_a_not_animal_mark(api_client, engine):
    # Issue #186: marking a detection not-animal from Photo Lookup must show
    # up as such on the next lookup too -- not just leave the flag set with
    # a stale identity/confidence still attached.
    with Session(engine) as session:
        asset = Asset(immich_asset_id="asset-not-animal", extension=".jpg")
        detection = Detection(
            asset=asset, label="dog", confidence=0.9, x1=0, y1=0, x2=1, y2=1
        )
        crop = Crop(detection=detection, path="crop.jpg", species=Species.DOG)
        classification = CropClassification(crop=crop, identity="Fibs", confidence=0.91)
        session.add(classification)
        session.commit()
        crop_id = crop.id

    mark_response = api_client.post(f"/crops/{crop_id}/not-animal")
    assert mark_response.status_code == 200

    response = api_client.get("/photo-lookup/asset-not-animal")

    assert response.status_code == 200
    detection = response.json()["detections"][0]
    assert detection["not_animal"] is True
    assert detection["identity"] is None


def test_photo_lookup_image_404_for_unscanned_asset(api_client):
    response = api_client.get("/photo-lookup/does-not-exist/image")

    assert response.status_code == 404


def test_photo_lookup_image_serves_the_original_as_jpeg(api_client, engine):
    with Session(engine) as session:
        _seed_asset_with_detection(session)

    fake_client = FakeImmichClient(
        content=_jpeg_bytes(Image.new("RGB", (200, 100), "white"))
    )
    api_client.app.dependency_overrides[get_immich_client] = lambda: fake_client

    response = api_client.get("/photo-lookup/asset-1/image")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
    assert Image.open(io.BytesIO(response.content)).size == (200, 100)
    assert fake_client.requested_asset_ids == ["asset-1"]


def test_photo_lookup_image_applies_exif_orientation(api_client, engine):
    # Issue #213: the displayed image must be decoded through the same
    # open_upright() path the detector used to produce `Detection.x1/y1/
    # x2/y2`, or the overlay boxes drift out of alignment with (or off of)
    # whatever ends up on screen. A landscape-stored, portrait-tagged
    # original (orientation 6) must come back upright, i.e. portrait.
    with Session(engine) as session:
        _seed_asset_with_detection(session, immich_asset_id="asset-rotated")

    fake_client = FakeImmichClient(
        content=_jpeg_bytes(Image.new("RGB", (200, 100), "white"), orientation=6)
    )
    api_client.app.dependency_overrides[get_immich_client] = lambda: fake_client

    response = api_client.get("/photo-lookup/asset-rotated/image")

    assert response.status_code == 200
    assert Image.open(io.BytesIO(response.content)).size == (100, 200)


def test_photo_lookup_image_is_jpeg_for_a_heic_original(api_client, engine):
    # Issue #206: a HEIC original must not be served as image/heic, which no
    # standard browser can render inline -- it's decoded and re-encoded to
    # JPEG regardless of the original's format, and the response's media
    # type must reflect that, not the original asset's stored extension.
    with Session(engine) as session:
        _seed_asset_with_detection(session, immich_asset_id="asset-heic")
        session.query(Asset).filter_by(immich_asset_id="asset-heic").update(
            {"extension": ".heic"}
        )
        session.commit()

    fake_client = FakeImmichClient(
        content=(_HEIC_FIXTURES_DIR / "heic_o6.heic").read_bytes()
    )
    api_client.app.dependency_overrides[get_immich_client] = lambda: fake_client

    response = api_client.get("/photo-lookup/asset-heic/image")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
    # Same orientation-6 fixture used in tests/test_images.py, where
    # open_upright() is asserted to swap it from stored (200, 100) to
    # upright (100, 200) -- confirms the HEIC path also goes through
    # open_upright() rather than being served as-is.
    assert Image.open(io.BytesIO(response.content)).size == (100, 200)


def test_photo_lookup_image_502_when_immich_fetch_fails(api_client, engine):
    with Session(engine) as session:
        _seed_asset_with_detection(session)

    fake_client = FakeImmichClient(error=ImmichDownloadError("boom"))
    api_client.app.dependency_overrides[get_immich_client] = lambda: fake_client

    response = api_client.get("/photo-lookup/asset-1/image")

    assert response.status_code == 502


def test_photo_lookup_image_502_when_immich_bytes_are_undecodable(api_client, engine):
    with Session(engine) as session:
        _seed_asset_with_detection(session)

    fake_client = FakeImmichClient(content=b"not-an-image")
    api_client.app.dependency_overrides[get_immich_client] = lambda: fake_client

    response = api_client.get("/photo-lookup/asset-1/image")

    assert response.status_code == 502
