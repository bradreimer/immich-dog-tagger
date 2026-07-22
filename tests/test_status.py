from sqlalchemy.orm import Session

from immich_dog_tagger.models import (
    Asset,
    Crop,
    CropClassification,
    Detection,
    Identity,
    EmbeddingExample,
    EmbeddingSources,
)

from immich_dog_tagger.services.status import StatusService


def test_status_summary(engine):
    with Session(engine) as session:
        asset = Asset(
            immich_asset_id="asset1",
            checksum="abc",
            extension=".jpg",
        )

        detection = Detection(
            asset=asset,
            label="dog",
            confidence=0.99,
            x1=0,
            y1=0,
            x2=100,
            y2=100,
        )

        crop = Crop(
            detection=detection,
            path="crop.jpg",
        )

        identity = Identity(
            name="Fibs",
        )

        example = EmbeddingExample(
            identity=identity,
            crop_path="example.jpg",
            embedding=b"123",
            source=EmbeddingSources.REVIEW,
        )

        classification = CropClassification(
            crop=crop,
            identity="Fibs",
            confidence=0.95,
        )

        session.add_all(
            [
                asset,
                detection,
                crop,
                identity,
                example,
                classification,
            ]
        )

        session.commit()

        summary = StatusService(session).summary()

        assert summary.assets == 1
        assert summary.detections == 1
        assert summary.crops == 1
        assert summary.classifications == 1
        assert summary.identities == 1
        assert summary.examples == 1
