from sqlalchemy.orm import Session

from immich_dog_tagger.enums import EmbeddingSources
from immich_dog_tagger.models import (
    EmbeddingExample,
    Identity,
)


def test_embedding_example_image(
    api_client,
    engine,
    tmp_path,
):
    image = tmp_path / "example.jpg"
    image.write_bytes(b"fake-image")

    with Session(engine) as session:
        identity = Identity(
            name="Hermann",
        )

        example = EmbeddingExample(
            identity=identity,
            crop_path=str(image),
            embedding=b"fake",
            source=EmbeddingSources.REVIEW,
        )

        session.add(example)
        session.commit()

        example_id = example.id

    response = api_client.get(
        f"/embedding-examples/{example_id}/image",
    )

    assert response.status_code == 200
    assert response.content == b"fake-image"
