from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from sqlalchemy.orm import Session

from immich_dog_tagger.classifier import IdentityClassifier
from immich_dog_tagger.embeddings import embedding_to_blob
from immich_dog_tagger.enums import (
    ClassificationSources,
    EmbeddingSources,
    ReviewActions,
    Species,
)
from immich_dog_tagger.models import (
    Asset,
    Crop,
    CropClassification,
    Detection,
    EmbeddingExample,
    Identity,
    ReviewAction,
)
from immich_dog_tagger.services.correction import ClassificationCorrectionService
from immich_dog_tagger.services.learner import Learner
from immich_dog_tagger.services.review_query import ReviewQueryService
from tests.conftest import create_test_classification


class FakeLearner:
    def __init__(self):
        self.calls = []

    def learn_image(
        self, identity, image_path, species=None, source=None, captured_at=None
    ):
        self.calls.append(
            {
                "identity": identity,
                "image_path": image_path,
                "species": species,
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
                "species": Species.DOG,
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
    classification = create_test_classification(session)

    classification.identity = "Fibs"
    session.commit()

    service = ClassificationCorrectionService(session)

    service.correct(
        classification.id,
        "Hermann",
    )

    action = session.query(ReviewAction).one()

    assert action.classification_id == classification.id
    assert action.action == ReviewActions.CORRECT
    assert action.original_identity == "Fibs"
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


def test_correction_learns_review_example_with_captured_at(engine, tmp_path):
    class FakeLearner:
        def __init__(self):
            self.calls = []

        def learn_image(
            self,
            identity,
            image_path,
            *,
            species=None,
            source,
            captured_at=None,
        ):
            self.calls.append(
                {
                    "identity": identity,
                    "image_path": image_path,
                    "species": species,
                    "source": source,
                    "captured_at": captured_at,
                }
            )

    image_path = tmp_path / "fibs.jpg"
    image_path.write_bytes(b"fake image")

    captured_at = datetime(2025, 1, 15, 12, 30, tzinfo=UTC)

    with Session(engine) as session:
        asset = Asset(
            immich_asset_id="asset-1",
            checksum="checksum",
            extension=".jpg",
            captured_at=captured_at,
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
            path=str(image_path),
        )

        classification = CropClassification(
            crop=crop,
            identity=None,
            confidence=0.5,
            candidates=[],
        )

        session.add(classification)
        session.commit()

        learner = FakeLearner()

        service = ClassificationCorrectionService(
            session,
            learner=learner,
        )

        service.correct(
            classification.id,
            "Fibs",
        )

        assert learner.calls == [
            {
                "identity": "Fibs",
                "image_path": image_path,
                "species": Species.DOG,
                "source": EmbeddingSources.REVIEW,
                "captured_at": captured_at.replace(tzinfo=None),
            }
        ]


def test_re_review_under_different_identity_supersedes_stale_example(engine, tmp_path):
    """DT-1003: re-reviewing a crop under a new identity must not leave the
    stale embedding example from the previous correction behind."""
    import numpy as np

    class FakeEmbedder:
        def embed(self, path):
            return np.array([1, 0, 0], dtype=np.float32)

    image_path = tmp_path / "dog.jpg"
    image_path.write_bytes(b"fake")

    with Session(engine) as session:
        crop = Crop(detection_id=1, path=str(image_path))
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

        learner = Learner(FakeEmbedder(), session)
        service = ClassificationCorrectionService(session, learner)

        service.correct(classification.id, "Fibs")
        service.correct(classification.id, "Hermann")

        examples = session.query(EmbeddingExample).all()

        assert len(examples) == 1
        assert examples[0].identity.name == "Hermann"

        result = session.get(CropClassification, classification.id)
        assert result.identity == "Hermann"


def test_correcting_to_unknown_removes_stale_embedding_example(engine, tmp_path):
    """DT-1003: correcting a crop to Unknown removes any reference example
    it previously contributed, instead of leaving stale learned data."""
    import numpy as np

    class FakeEmbedder:
        def embed(self, path):
            return np.array([1, 0, 0], dtype=np.float32)

    image_path = tmp_path / "dog.jpg"
    image_path.write_bytes(b"fake")

    with Session(engine) as session:
        crop = Crop(detection_id=1, path=str(image_path))
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

        learner = Learner(FakeEmbedder(), session)
        service = ClassificationCorrectionService(session, learner)

        service.correct(classification.id, "Fibs")
        assert session.query(EmbeddingExample).count() == 1

        service.correct(classification.id, "Unknown")

        assert session.query(EmbeddingExample).count() == 0

        result = session.get(CropClassification, classification.id)
        assert result.identity == "Unknown"


def test_correct_species_rescores_against_new_species_pool(engine):
    with Session(engine) as session:
        # A dog "Max" and a cat "Max" whose examples would be each other's
        # nearest neighbor if species scoping were broken.
        dog_max = Identity(name="Max", species=Species.DOG)
        cat_max = Identity(name="Max", species=Species.CAT)
        session.add_all([dog_max, cat_max])
        session.flush()

        session.add(
            EmbeddingExample(
                identity_id=dog_max.id,
                crop_path="dog-max.jpg",
                embedding=embedding_to_blob(np.array([0, 1, 0], dtype=np.float32)),
                source=EmbeddingSources.BOOTSTRAP,
            )
        )
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
            source=ClassificationSources.AUTO,
            embedding=embedding_to_blob(np.array([0.95, 0.05, 0], dtype=np.float32)),
        )
        session.add(classification)
        session.commit()

        service = ClassificationCorrectionService(
            session,
            classifier=IdentityClassifier(session),
        )

        result = service.correct_species(classification.id, Species.CAT)

        assert crop.species == Species.CAT
        assert result.identity == "Max"
        assert result.similarity > 0.9
        assert result.source == ClassificationSources.AUTO

        # No ReviewAction should be written -- a species correction doesn't
        # decide an identity, so it must not mark the item as reviewed and
        # drop it from the active review queue.
        assert session.query(ReviewAction).count() == 0


def test_correct_species_noop_when_unchanged(engine):
    with Session(engine) as session:
        crop = Crop(detection_id=1, path="dog.jpg", species=Species.DOG)
        session.add(crop)
        session.flush()

        classification = CropClassification(
            crop=crop,
            identity="Hermann",
            confidence=0.95,
            source=ClassificationSources.REVIEW,
            embedding=embedding_to_blob(np.array([1, 0, 0], dtype=np.float32)),
        )
        session.add(classification)
        session.commit()

        service = ClassificationCorrectionService(session)

        result = service.correct_species(classification.id, Species.DOG)

        assert result.identity == "Hermann"
        assert result.confidence == 0.95
        assert result.source == ClassificationSources.REVIEW


def test_correct_species_forgets_stale_learning_example(engine, tmp_path):
    image_path = tmp_path / "dog.jpg"
    image_path.write_bytes(b"fake")

    with Session(engine) as session:
        dog_hermann = Identity(name="Hermann", species=Species.DOG)
        session.add(dog_hermann)
        session.flush()

        session.add(
            EmbeddingExample(
                identity_id=dog_hermann.id,
                crop_path=str(image_path),
                embedding=embedding_to_blob(np.array([1, 0, 0], dtype=np.float32)),
                source=EmbeddingSources.REVIEW,
            )
        )

        crop = Crop(detection_id=1, path=str(image_path), species=Species.DOG)
        session.add(crop)
        session.flush()

        classification = CropClassification(
            crop=crop,
            identity="Hermann",
            confidence=1.0,
            source=ClassificationSources.REVIEW,
            embedding=embedding_to_blob(np.array([1, 0, 0], dtype=np.float32)),
        )
        session.add(classification)
        session.commit()

        learner = Learner(embedder=None, session=session)
        service = ClassificationCorrectionService(session, learner=learner)

        service.correct_species(classification.id, Species.CAT)

        assert session.query(EmbeddingExample).count() == 0


def test_correct_species_rejects_unknown_classification(engine):
    with Session(engine) as session:
        service = ClassificationCorrectionService(session)

        try:
            service.correct_species(999, Species.CAT)
        except ValueError as exc:
            assert str(exc) == "Classification 999 not found"
        else:
            raise AssertionError("Expected ValueError")
