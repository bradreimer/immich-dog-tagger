from pathlib import Path
from sqlalchemy.orm import Session

from immich_dog_tagger.models import (
    ClassificationSources,
    Crop,
    CropClassification,
    EmbeddingSources,
    EmbeddingExample,
)
from immich_dog_tagger.services.correction import ClassificationCorrectionService
from immich_dog_tagger.services.learner import Learner


class FakeLearner:
    def __init__(self):
        self.calls = []

    def learn_image(self, identity, path, source):
        self.calls.append((identity, path, source))


def test_correction_marks_classification_as_review(engine):
    with Session(engine) as session:
        crop = Crop(
            detection_id=1,
            path="test.jpg",
        )

        classification = CropClassification(
            crop=crop,
            identity=None,
            confidence=0.4,
        )

        session.add(classification)
        session.commit()

        service = ClassificationCorrectionService(session)

        service.correct(
            classification.id,
            "Hermann",
        )

        session.commit()

        result = session.get(
            CropClassification,
            classification.id,
        )

        assert result.identity == "Hermann"
        assert result.source == ClassificationSources.REVIEW


def test_correction_rejects_unknown_classification(engine):
    with Session(engine) as session:
        service = ClassificationCorrectionService(session)

        try:
            service.correct(
                999,
                "Hermann",
            )
        except ValueError as exc:
            assert str(exc) == "Classification 999 not found"
        else:
            raise AssertionError("Expected ValueError")


def test_correction_learns_from_review(engine):
    from sqlalchemy.orm import Session

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

        learner = FakeLearner()

        service = ClassificationCorrectionService(
            session,
            learner,
        )

        service.correct(
            classification.id,
            "Hermann",
        )

        assert learner.calls == [
            (
                "Hermann",
                Path("hermann.jpg"),
                EmbeddingSources.REVIEW,
            )
        ]


def test_correction_creates_embedding_example(
    engine,
):
    from unittest.mock import Mock

    with Session(engine) as session:
        crop = Crop(
            detection_id=1,
            path="fib.jpg",
        )

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

        learner = Mock()

        service = ClassificationCorrectionService(
            session,
            learner,
        )

        service.correct(
            classification.id,
            "Fibs",
        )

        learner.learn_image.assert_called_once()

        result = session.query(CropClassification).one()

        assert result.identity == "Fibs"
        assert result.source == ClassificationSources.REVIEW


def test_correction_creates_review_embedding_example(
    engine,
):
    import numpy as np

    class FakeEmbedder:
        def embed(self, path):
            return np.array(
                [1, 0, 0],
                dtype=np.float32,
            )

    with Session(engine) as session:
        crop = Crop(
            detection_id=1,
            path="fib.jpg",
        )

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

        learner = Learner(
            FakeEmbedder(),
            session,
        )

        service = ClassificationCorrectionService(
            session,
            learner,
        )

        service.correct(
            classification.id,
            "Fibs",
        )

        examples = session.query(EmbeddingExample).all()

        assert len(examples) == 1
        assert examples[0].crop_path == "fib.jpg"
        assert examples[0].source == EmbeddingSources.REVIEW


def test_correction_apply_updates_classification(engine):

    with Session(engine) as session:
        crop = Crop(
            detection_id=1,
            path="test.jpg",
        )

        session.add(crop)
        session.flush()

        classification = CropClassification(
            crop=crop,
            identity=None,
            confidence=0.4,
            source=ClassificationSources.AUTO,
        )

        session.add(classification)
        session.commit()

        service = ClassificationCorrectionService(
            session,
            FakeLearner(),
        )

        result = service.correct(
            classification.id,
            "Hermann",
        )

        session.commit()

        assert result.identity == "Hermann"
        assert result.source == ClassificationSources.REVIEW


def test_correction_apply_teaches_learner(engine):
    from unittest.mock import Mock

    with Session(engine) as session:
        crop = Crop(
            detection_id=1,
            path="test.jpg",
        )

        session.add(crop)
        session.flush()

        classification = CropClassification(
            crop=crop,
            identity=None,
            confidence=0.4,
            source=ClassificationSources.AUTO,
        )

        session.add(classification)
        session.commit()

        learner = Mock()

        service = ClassificationCorrectionService(
            session,
            learner,
        )

        service.correct(
            classification.id,
            "Hermann",
        )

        learner.learn_image.assert_called_once()
