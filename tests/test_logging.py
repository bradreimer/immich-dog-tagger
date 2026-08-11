"""DT-1007: verify pipeline/reclassification/correction lifecycle logging."""

import logging

from sqlalchemy.orm import Session

from immich_dog_tagger.enums import ClassificationSources, PipelineOperation
from immich_dog_tagger.models import Crop, CropClassification
from immich_dog_tagger.services.correction import ClassificationCorrectionService
from immich_dog_tagger.services.job_runner import PipelineJobRunner
from immich_dog_tagger.services.jobs import PipelineJobRepository, PipelineJobService


def _build_runner(session, handlers):
    repository = PipelineJobRepository(session)
    service = PipelineJobService(session, repository=repository)
    return PipelineJobRunner(repository=repository, service=service, handlers=handlers)


def test_job_success_is_logged(engine, caplog):
    with Session(engine) as session:
        service = PipelineJobService(session)
        job = service.create_job(operation=PipelineOperation.SCAN)

        runner = _build_runner(
            session, {PipelineOperation.SCAN: lambda progress: {"scanned": 1}}
        )

        with caplog.at_level(
            logging.INFO, logger="immich_dog_tagger.services.job_runner"
        ):
            runner.run_job(job.id)

    assert any("started" in message for message in caplog.messages)
    assert any("completed" in message for message in caplog.messages)


def test_job_failure_is_logged(engine, caplog):
    with Session(engine) as session:
        service = PipelineJobService(session)
        job = service.create_job(operation=PipelineOperation.DETECT)

        def failing_handler(progress):
            raise RuntimeError("boom")

        runner = _build_runner(session, {PipelineOperation.DETECT: failing_handler})

        with caplog.at_level(
            logging.INFO, logger="immich_dog_tagger.services.job_runner"
        ):
            try:
                runner.run_job(job.id)
            except RuntimeError:
                pass

    assert any("failed" in message and "boom" in message for message in caplog.messages)
    # No image paths/content should ever appear in job lifecycle logs.
    assert not any(".jpg" in message for message in caplog.messages)


def test_correction_is_logged_without_image_content(engine, caplog):
    with Session(engine) as session:
        crop = Crop(detection_id=1, path="private/photo-of-my-dog.jpg")
        session.add(crop)
        session.flush()

        classification = CropClassification(
            crop=crop,
            identity=None,
            confidence=0.2,
            source=ClassificationSources.AUTO,
        )
        session.add(classification)
        session.commit()

        service = ClassificationCorrectionService(session)

        with caplog.at_level(
            logging.INFO, logger="immich_dog_tagger.services.correction"
        ):
            service.correct(classification.id, "Hermann")

    assert any(
        f"Classification {classification.id} corrected" in message
        for message in caplog.messages
    )
    assert any("Hermann" in message for message in caplog.messages)
    # The crop's file path must never be logged.
    assert not any("photo-of-my-dog" in message for message in caplog.messages)
