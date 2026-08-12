from sqlalchemy import select
from sqlalchemy.orm import Session

from immich_dog_tagger.enums import (
    ClassificationSources,
    ReviewActions,
)
from immich_dog_tagger.models import (
    Crop,
    CropClassification,
    ReviewAction,
)


def test_correct_classification(api_client, engine):
    with Session(engine) as session:
        crop = Crop(
            detection_id=1,
            path="hermann.jpg",
        )

        classification = CropClassification(
            crop=crop,
            identity=None,
            confidence=0.4,
        )

        session.add(classification)
        session.commit()

        classification_id = classification.id

    response = api_client.post(
        f"/classifications/{classification_id}/correct",
        json={
            "identity": "Hermann",
        },
    )

    assert response.status_code == 200

    with Session(engine) as session:
        updated = session.get(
            CropClassification,
            classification_id,
        )

        assert updated is not None
        assert updated.identity == "Hermann"
        assert updated.confidence == 1.0
        assert updated.source == ClassificationSources.REVIEW

        action = session.scalar(
            select(ReviewAction).where(
                ReviewAction.classification_id == classification_id,
                ReviewAction.action == ReviewActions.CORRECT,
            )
        )

        assert action is not None
        assert action.identity == "Hermann"


def test_correct_classification_with_stored_embedding_serializes_response(
    api_client, engine
):
    # Regression test: CropClassification.embedding is a raw (non-UTF-8) binary blob in
    # production -- returning the ORM object directly used to reach FastAPI's default
    # jsonable_encoder, which blindly calls bytes.decode() and raised UnicodeDecodeError
    # for any embedding whose bytes weren't valid UTF-8 (as float32 embedding bytes
    # essentially never are). The route must build an explicit response schema instead.
    with Session(engine) as session:
        crop = Crop(
            detection_id=1,
            path="hermann.jpg",
        )

        classification = CropClassification(
            crop=crop,
            identity=None,
            confidence=0.4,
            embedding=bytes([0x00, 0x01, 0xC5, 0xFF, 0x10]),
        )

        session.add(classification)
        session.commit()

        classification_id = classification.id
        crop_id = crop.id

    response = api_client.post(
        f"/classifications/{classification_id}/correct",
        json={
            "identity": "Hermann",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "classification_id": classification_id,
        "crop_id": crop_id,
        "identity": "Hermann",
        "confidence": 1.0,
        "filename": "hermann.jpg",
    }


def test_correct_classification_not_found(api_client):
    response = api_client.post(
        "/classifications/999999/correct",
        json={
            "identity": "Hermann",
        },
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Classification 999999 not found",
    }
