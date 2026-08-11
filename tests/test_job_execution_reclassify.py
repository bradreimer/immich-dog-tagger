import numpy as np
from sqlalchemy.orm import Session

from immich_dog_tagger.embeddings import embedding_to_blob
from immich_dog_tagger.enums import PipelineOperation
from immich_dog_tagger.models import (
    ClassificationPass,
    Crop,
    CropClassification,
    EmbeddingExample,
    EmbeddingSources,
    Identity,
)
from immich_dog_tagger.services.job_execution import (
    _reclassify_handler,
    create_pipeline_job_runner,
)
from immich_dog_tagger.services.jobs import PipelineJobService


class DummyProgress:
    def set(self, current=None, total=None, message=None):
        return None

    def message(self, value):
        return None


class FakeEmbedder:
    def embed_batch(self, paths):
        return np.array([[1, 0, 0] for _ in paths], dtype=np.float32)


def _seed_reclassifiable_crop(session):
    identity = Identity(name="Hermann")
    session.add(identity)
    session.flush()

    session.add(
        EmbeddingExample(
            identity_id=identity.id,
            crop_path="hermann.jpg",
            embedding=embedding_to_blob(np.array([1, 0, 0], dtype=np.float32)),
            source=EmbeddingSources.BOOTSTRAP,
        )
    )

    crop = Crop(detection_id=1, path="new.jpg")
    session.add(crop)
    session.flush()

    session.add(
        CropClassification(
            crop=crop,
            identity=None,
            confidence=-1.0,
            embedding=embedding_to_blob(np.array([1, 0, 0], dtype=np.float32)),
        )
    )
    session.commit()


def test_reclassify_handler_updates_predictions(engine, monkeypatch):
    monkeypatch.setattr(
        "immich_dog_tagger.services.job_execution.get_embedder",
        lambda: FakeEmbedder(),
    )

    with Session(engine) as session:
        _seed_reclassifiable_crop(session)

        handler = _reclassify_handler(session, {})
        result = handler(DummyProgress())

    assert result["status"] == "completed"
    assert result["eligible_count"] == 1
    assert result["confident_count"] == 1

    with Session(engine) as session:
        classification = session.query(CropClassification).one()
        assert classification.identity == "Hermann"


def test_reclassify_runs_through_pipeline_job_runner(engine, monkeypatch):
    monkeypatch.setattr(
        "immich_dog_tagger.services.job_execution.get_embedder",
        lambda: FakeEmbedder(),
    )

    with Session(engine) as session:
        _seed_reclassifiable_crop(session)

        from pathlib import Path

        from immich_dog_tagger.config import Config

        config = Config(
            immich_url="",
            immich_api_key="",
            state_dir=Path("state"),
            cache_dir=Path("cache"),
            yolo_model=Path("yolo11n.pt"),
            crop_padding=0.15,
        )

        runner = create_pipeline_job_runner(session, config)
        service = PipelineJobService(session, repository=runner.repository)
        job = service.create_job(operation=PipelineOperation.RECLASSIFY)

        result = runner.run_job(job.id)

        session.refresh(job)
        assert job.status.value == "completed"
        assert result["eligible_count"] == 1

        classification_pass = session.query(ClassificationPass).one()
        assert classification_pass.confident_count == 1
