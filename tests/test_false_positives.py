"""
Issue #185: marking a Photo Lookup detection as "not a dog or cat". Issue
#186 follow-up: marking must actually settle the classification, not just
flip the flag -- otherwise Library keeps showing "Confirmed as <Dog>" and
sync keeps the photo in that dog's Immich album.
"""

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from immich_dog_tagger.enums import ClassificationSources, EmbeddingSources, Species
from immich_dog_tagger.models import (
    Asset,
    Crop,
    CropClassification,
    Detection,
    EmbeddingExample,
    Identity,
    PetOccurrence,
    ReviewAction,
)
from immich_dog_tagger.services.correction import ClassificationCorrectionService
from immich_dog_tagger.services.false_positives import FalsePositiveService


class FakeLearner:
    """Records forget_image calls; the real Learner needs an embedder."""

    def __init__(self, session):
        self.session = session
        self.forgotten = []

    def forget_image(self, image_path):
        self.forgotten.append(str(image_path))

        examples = self.session.scalars(
            select(EmbeddingExample).where(
                EmbeddingExample.crop_path == str(image_path)
            )
        ).all()

        for example in examples:
            self.session.delete(example)

        return len(examples)


def _service(session, learner=None):
    return FalsePositiveService(
        session,
        ClassificationCorrectionService(session, learner=learner),
    )


def test_mark_sets_flag_when_crop_has_no_classification(engine):
    with Session(engine) as session:
        crop = Crop(detection_id=1, path="crop.jpg")
        session.add(crop)
        session.commit()

        marked = _service(session).mark(crop.id)

        assert marked.not_animal is True


def test_mark_settles_classification_to_unknown(engine):
    with Session(engine) as session:
        crop = Crop(detection_id=1, path="crop.jpg", species=Species.DOG)
        classification = CropClassification(
            crop=crop,
            identity="Fibs",
            confidence=0.91,
            source=ClassificationSources.AUTO,
        )
        session.add(classification)
        session.commit()
        classification_id = classification.id

        marked = _service(session).mark(crop.id)

        assert marked.not_animal is True

        result = session.get(CropClassification, classification_id)
        assert result.identity is None
        assert result.confidence == 1.0
        assert result.source == ClassificationSources.REVIEW

        action = session.scalars(
            select(ReviewAction).where(
                ReviewAction.classification_id == classification_id
            )
        ).one()
        assert action.original_identity == "Fibs"
        assert action.identity is None


def test_mark_clears_pet_occurrence(engine):
    with Session(engine) as session:
        identity = Identity(species=Species.DOG, name="Fibs")
        session.add(identity)
        session.commit()

        asset = Asset(immich_asset_id="asset-1", extension=".jpg")
        detection = Detection(
            asset=asset, label="dog", confidence=0.9, x1=0, y1=0, x2=1, y2=1
        )
        crop = Crop(detection=detection, path="crop.jpg", species=Species.DOG)
        classification = CropClassification(crop=crop, identity="Fibs", confidence=0.91)
        session.add(classification)
        session.commit()

        session.add(
            PetOccurrence(
                crop_classification_id=classification.id,
                asset_id=asset.id,
                identity_id=identity.id,
                confidence=0.91,
                source=ClassificationSources.AUTO,
            )
        )
        session.commit()

        _service(session).mark(crop.id)

        assert session.scalars(select(PetOccurrence)).first() is None


def test_mark_forgets_learned_reference(engine):
    with Session(engine) as session:
        crop = Crop(detection_id=1, path="crop.jpg", species=Species.DOG)
        classification = CropClassification(crop=crop, identity="Fibs", confidence=0.91)
        session.add(classification)
        session.commit()

        identity = Identity(species=Species.DOG, name="Fibs")
        session.add(identity)
        session.commit()

        example = EmbeddingExample(
            identity_id=identity.id,
            crop_path="crop.jpg",
            embedding=b"\x00" * 4,
            source=EmbeddingSources.REVIEW,
        )
        session.add(example)
        session.commit()

        learner = FakeLearner(session)
        _service(session, learner=learner).mark(crop.id)

        assert learner.forgotten == ["crop.jpg"]
        assert session.get(EmbeddingExample, example.id) is None


def test_mark_is_idempotent(engine):
    with Session(engine) as session:
        crop = Crop(detection_id=1, path="crop.jpg", species=Species.DOG)
        classification = CropClassification(crop=crop, identity="Fibs", confidence=0.91)
        session.add(classification)
        session.commit()
        classification_id = classification.id

        service = _service(session)
        service.mark(crop.id)
        service.mark(crop.id)

        actions = session.scalars(
            select(ReviewAction).where(
                ReviewAction.classification_id == classification_id
            )
        ).all()
        assert len(actions) == 1


def test_unmark_clears_flag_but_leaves_classification_settled(engine):
    with Session(engine) as session:
        crop = Crop(detection_id=1, path="crop.jpg", species=Species.DOG)
        classification = CropClassification(crop=crop, identity="Fibs", confidence=0.91)
        session.add(classification)
        session.commit()
        classification_id = classification.id

        service = _service(session)
        service.mark(crop.id)
        unmarked = service.unmark(crop.id)

        assert unmarked.not_animal is False

        result = session.get(CropClassification, classification_id)
        assert result.identity is None


def test_mark_unknown_crop_raises(engine):
    with Session(engine) as session, pytest.raises(ValueError, match="999999"):
        _service(session).mark(999999)


def test_unmark_unknown_crop_raises(engine):
    with Session(engine) as session, pytest.raises(ValueError, match="999999"):
        _service(session).unmark(999999)
