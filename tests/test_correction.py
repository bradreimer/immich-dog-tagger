from pathlib import Path

from sqlalchemy.orm import Session

from immich_dog_tagger.enums import (
    ClassificationSources,
    EmbeddingSources,
    ReviewActions,
)
from immich_dog_tagger.models import (
    Crop,
    CropClassification,
    EmbeddingExample,
    ReviewAction,
)
from immich_dog_tagger.services.correction import ClassificationCorrectionService
from immich_dog_tagger.services.learner import Learner
from immich_dog_tagger.services.review_query import ReviewQueryService
from tests.conftest import create_test_classification


class FakeLearner:
    def __init__(self):
        self.calls = []

    def learn_image(self, identity, image_path, source, captured_at=None):
        self.calls.append(
            {
                "identity": identity,
                "image_path": image_path,
                "source": source,
                "captured_at": captured_at,
            }
        )


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
        assert result.confidence == 1.0
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
            {
                "identity": "Hermann",
                "image_path": Path("hermann.jpg"),
                "source": EmbeddingSources.REVIEW,
                "captured_at": None,
            }
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
        assert result.confidence == 1.0
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
        assert result.confidence == 1.0
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


def test_duplicate_correction_does_not_duplicate_embedding_example(
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

        service.correct(
            classification.id,
            "Fibs",
        )

        examples = session.query(EmbeddingExample).all()

        assert len(examples) == 1


def test_correction_creates_review_action(session):
    service = ClassificationCorrectionService(session)

    classification = create_test_classification(session)

    service.correct(
        classification.id,
        "Hermann",
    )

    action = session.query(ReviewAction).one()

    assert action.classification_id == classification.id
    assert action.action == ReviewActions.CORRECT
    assert action.identity == "Hermann"


def test_skipped_review_item_not_returned(session):
    classification = create_test_classification(session)

    session.add(
        ReviewAction(
            classification_id=classification.id,
            action=ReviewActions.SKIP,
        )
    )

    session.commit()

    service = ReviewQueryService(session)

    items = service.active_review()

    assert classification.id not in [item.classification_id for item in items]
