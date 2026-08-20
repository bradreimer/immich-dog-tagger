from concurrent.futures import ThreadPoolExecutor

from sqlalchemy.orm import Session

from immich_dog_tagger.models import Crop


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
