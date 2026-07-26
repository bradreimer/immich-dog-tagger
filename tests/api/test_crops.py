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
