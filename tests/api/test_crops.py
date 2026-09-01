from concurrent.futures import ThreadPoolExecutor

from sqlalchemy.orm import Session

from immich_dog_tagger.enums import AssetStatus
from immich_dog_tagger.models import Asset, Crop, CropClassification, Detection


def test_get_crop_image(api_client, engine, tmp_path):
    image = tmp_path / "crop.jpg"
    image.write_bytes(b"fake-jpeg-data")

    with Session(engine) as session:
        crop = Crop(
            detection_id=1,
            path=str(image),
        )

        session.add(crop)
        session.commit()

        crop_id = crop.id

    response = api_client.get(
        f"/crops/{crop_id}",
    )

    assert response.status_code == 200
    assert response.content == b"fake-jpeg-data"


def test_get_crop_image_not_found(api_client):
    response = api_client.get(
        "/crops/999999",
    )

    assert response.status_code == 404


def test_get_crop_image_404s_for_a_removed_asset(api_client, engine, tmp_path):
    # Issue #194/FR-3: the source photo was deleted in Immich and
    # reconciled out -- serve a clean 404, not the (possibly already
    # cleaned-up) crop file.
    image = tmp_path / "crop.jpg"
    image.write_bytes(b"fake-jpeg-data")

    with Session(engine) as session:
        asset = Asset(
            immich_asset_id="removed-1",
            checksum="a",
            extension=".jpg",
            status=AssetStatus.REMOVED,
        )
        session.add(asset)
        session.flush()

        detection = Detection(
            asset_id=asset.id,
            label="dog",
            confidence=0.9,
            x1=0,
            y1=0,
            x2=1,
            y2=1,
        )
        session.add(detection)
        session.flush()

        crop = Crop(detection_id=detection.id, path=str(image))
        session.add(crop)
        session.commit()

        crop_id = crop.id

    response = api_client.get(f"/crops/{crop_id}")

    assert response.status_code == 404


def test_mark_crop_not_animal(api_client, engine):
    with Session(engine) as session:
        crop = Crop(detection_id=1, path="crop.jpg")
        session.add(crop)
        session.commit()
        crop_id = crop.id

    response = api_client.post(f"/crops/{crop_id}/not-animal")

    assert response.status_code == 200
    assert response.json() == {"crop_id": crop_id, "not_animal": True}

    with Session(engine) as session:
        assert session.get(Crop, crop_id).not_animal is True


def test_mark_crop_not_animal_settles_its_classification(api_client, engine):
    # Issue #186: marking must clear the identity too, or the crop keeps
    # showing "Confirmed as <Dog>" in Library and stays in that dog's
    # Immich album on the next sync.
    with Session(engine) as session:
        crop = Crop(detection_id=1, path="crop.jpg")
        classification = CropClassification(crop=crop, identity="Fibs", confidence=0.91)
        session.add(classification)
        session.commit()
        crop_id = crop.id
        classification_id = classification.id

    response = api_client.post(f"/crops/{crop_id}/not-animal")

    assert response.status_code == 200

    with Session(engine) as session:
        result = session.get(CropClassification, classification_id)
        assert result.identity is None


def test_mark_crop_not_animal_404_for_unknown_crop(api_client):
    response = api_client.post("/crops/999999/not-animal")

    assert response.status_code == 404


def test_unmark_crop_not_animal(api_client, engine):
    with Session(engine) as session:
        crop = Crop(detection_id=1, path="crop.jpg", not_animal=True)
        session.add(crop)
        session.commit()
        crop_id = crop.id

    response = api_client.delete(f"/crops/{crop_id}/not-animal")

    assert response.status_code == 200
    assert response.json() == {"crop_id": crop_id, "not_animal": False}

    with Session(engine) as session:
        assert session.get(Crop, crop_id).not_animal is False


def test_unmark_crop_not_animal_404_for_unknown_crop(api_client):
    response = api_client.delete("/crops/999999/not-animal")

    assert response.status_code == 404


def test_get_crop_image_survives_a_burst_of_concurrent_requests(
    api_client, engine, tmp_path
):
    # Regression test for issue #164: opening the Library tab for a dog with
    # many pending photos fires dozens of near-simultaneous GET /crops/{id}
    # thumbnail requests. This burst (30) is well beyond the old pool's
    # 15-connection ceiling, which used to leave overflow requests blocking
    # on the connection pool and eventually failing with a 500
    # (sqlalchemy.exc.TimeoutError) instead of every crop loading.
    image = tmp_path / "crop.jpg"
    image.write_bytes(b"fake-jpeg-data")

    crop_ids = []

    with Session(engine) as session:
        for _ in range(30):
            crop = Crop(detection_id=1, path=str(image))
            session.add(crop)
            session.flush()
            crop_ids.append(crop.id)

        session.commit()

    with ThreadPoolExecutor(max_workers=len(crop_ids)) as executor:
        responses = list(
            executor.map(lambda crop_id: api_client.get(f"/crops/{crop_id}"), crop_ids)
        )

    assert [response.status_code for response in responses] == [200] * len(crop_ids)
    assert all(response.content == b"fake-jpeg-data" for response in responses)
