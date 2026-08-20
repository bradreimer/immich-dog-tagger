import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from immich_dog_tagger.embeddings import embedding_to_blob
from immich_dog_tagger.enums import (
    ClassificationSources,
    ReviewActions,
    Species,
)
from immich_dog_tagger.models import (
    Crop,
    CropClassification,
    EmbeddingExample,
    EmbeddingSources,
    Identity,
    ReviewAction,
)
from tests.conftest import create_test_classification


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


def test_correct_species(api_client, engine):
    with Session(engine) as session:
        cat_max = Identity(name="Max", species=Species.CAT)
        session.add(cat_max)
        session.flush()

        session.add(
            EmbeddingExample(
                identity_id=cat_max.id,
                crop_path="cat-max.jpg",
                embedding=embedding_to_blob(np.array([1, 0, 0], dtype=np.float32)),
                source=EmbeddingSources.BOOTSTRAP,
            )
        )

        crop = Crop(detection_id=1, path="mystery.jpg", species=Species.DOG)
        session.add(crop)
        session.flush()

        classification = CropClassification(
            crop=crop,
            identity=None,
            confidence=-1.0,
            embedding=embedding_to_blob(np.array([0.95, 0.05, 0], dtype=np.float32)),
        )
        session.add(classification)
        session.commit()

        classification_id = classification.id
        crop_id = crop.id

    response = api_client.post(
        f"/classifications/{classification_id}/species",
        json={
            "species": "cat",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["classification_id"] == classification_id
    assert body["crop_id"] == crop_id
    assert body["species"] == "cat"
    assert body["prediction"]["identity"] == "Max"

    with Session(engine) as session:
        updated_crop = session.get(Crop, crop_id)
        assert updated_crop.species == Species.CAT

        # No ReviewAction: the item still needs a human identity decision.
        assert session.query(ReviewAction).count() == 0


def test_correct_species_not_found(api_client):
    response = api_client.post(
        "/classifications/999999/species",
        json={
            "species": "cat",
        },
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Classification 999999 not found",
    }


def test_correcting_queues_an_automatic_reclassify(api_client, engine):
    """
    Issue #149: the owner just settled an identity, so the predictions
    derived from the reference set are stale. Queued through the job system
    so work the app started on its own is as visible as work the owner
    started (ADR-006).
    """
    from immich_dog_tagger.enums import PipelineOperation
    from immich_dog_tagger.models import PipelineJob

    with Session(engine) as session:
        classification = create_test_classification(session)
        classification_id = classification.id

    api_client.post(
        f"/classifications/{classification_id}/correct",
        json={"identity": "Fibs"},
    )

    with Session(engine) as session:
        jobs = (
            session.query(PipelineJob)
            .filter(PipelineJob.operation == PipelineOperation.RECLASSIFY)
            .all()
        )

        assert len(jobs) == 1


def test_repeated_corrections_queue_only_one_reclassify(api_client, engine):
    from immich_dog_tagger.enums import PipelineOperation
    from immich_dog_tagger.models import PipelineJob

    with Session(engine) as session:
        first = create_test_classification(session).id
        second = create_test_classification(session).id

    for classification_id in (first, second):
        api_client.post(
            f"/classifications/{classification_id}/correct",
            json={"identity": "Fibs"},
        )

    with Session(engine) as session:
        jobs = (
            session.query(PipelineJob)
            .filter(PipelineJob.operation == PipelineOperation.RECLASSIFY)
            .all()
        )

        assert len(jobs) == 1
