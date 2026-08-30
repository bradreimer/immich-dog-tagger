"""
Issue #185: marking a Photo Lookup detection as "not a dog or cat".
"""

import pytest
from sqlalchemy.orm import Session

from immich_dog_tagger.models import Crop
from immich_dog_tagger.services.false_positives import FalsePositiveService


def test_mark_sets_not_animal(engine):
    with Session(engine) as session:
        crop = Crop(detection_id=1, path="crop.jpg")
        session.add(crop)
        session.commit()

        marked = FalsePositiveService(session).mark(crop.id)

        assert marked.not_animal is True
        assert session.get(Crop, crop.id).not_animal is True


def test_mark_is_idempotent(engine):
    with Session(engine) as session:
        crop = Crop(detection_id=1, path="crop.jpg")
        session.add(crop)
        session.commit()

        service = FalsePositiveService(session)
        service.mark(crop.id)
        service.mark(crop.id)

        assert session.get(Crop, crop.id).not_animal is True


def test_unmark_clears_not_animal(engine):
    with Session(engine) as session:
        crop = Crop(detection_id=1, path="crop.jpg", not_animal=True)
        session.add(crop)
        session.commit()

        unmarked = FalsePositiveService(session).unmark(crop.id)

        assert unmarked.not_animal is False
        assert session.get(Crop, crop.id).not_animal is False


def test_mark_unknown_crop_raises(engine):
    with Session(engine) as session, pytest.raises(ValueError, match="999999"):
        FalsePositiveService(session).mark(999999)


def test_unmark_unknown_crop_raises(engine):
    with Session(engine) as session, pytest.raises(ValueError, match="999999"):
        FalsePositiveService(session).unmark(999999)
