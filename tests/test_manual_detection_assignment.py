"""
Issue #261: manually map a crop-less or mislabeled detection (YOLO labeled
it outside {dog, cat}, so the pipeline never created a crop for it) to a
dog/cat identity, or confirm it's not one -- without depending on an
automatic classifier run. See `docs/specs/photo-lookup.md`'s "manually map
a crop-less or mislabeled detection" addendum.
"""

import numpy as np
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from immich_dog_tagger.enums import ClassificationSources, ReviewActions, Species
from immich_dog_tagger.models import (
    Asset,
    Crop,
    CropClassification,
    Detection,
    ReviewAction,
)
from immich_dog_tagger.services.correction import ClassificationCorrectionService
from immich_dog_tagger.services.false_positives import FalsePositiveService
from immich_dog_tagger.services.manual_detection_assignment import (
    ManualDetectionAssignmentService,
)


class FakeImmichClient:
    def __init__(self, content: bytes = b"image data"):
        self.content = content
        self.requested_asset_ids: list[str] = []

    def download_asset(self, asset_id: str) -> bytes:
        self.requested_asset_ids.append(asset_id)
        return self.content


class FakeEmbedder:
    def embed(self, path):
        return np.array([1.0, 0.0, 0.0], dtype=np.float32)


class FakeCropWriter:
    """
    Stands in for the real `CropWriter` (which needs a real, decodable
    image) so these tests exercise `ManualDetectionAssignmentService`'s own
    logic -- crop-less/already-cropped checks, the classification/
    ReviewAction/not-animal handoff -- without depending on Pillow actually
    decoding fake `b"image data"` bytes. `crop_one()`'s own
    padding/degenerate-box behavior is already covered by
    `tests/test_crops.py`.
    """

    def __init__(self, tmp_path):
        self.crop_dir = tmp_path
        self.degenerate = False

    def crop_one(self, image, x1, y1, x2, y2, context=""):
        if self.degenerate:
            return None

        return image


class FakeImage:
    def convert(self, mode):
        return self

    def save(self, path):
        from pathlib import Path

        Path(path).write_bytes(b"crop bytes")


def _build_service(session, tmp_path, *, client=None, crop_writer=None):
    client = client or FakeImmichClient()
    crop_writer = crop_writer or FakeCropWriter(tmp_path)

    correction_service = ClassificationCorrectionService(session, learner=None)
    false_positive_service = FalsePositiveService(session, correction_service)

    service = ManualDetectionAssignmentService(
        session=session,
        client=client,
        embedder=FakeEmbedder(),
        crop_writer=crop_writer,
        correction_service=correction_service,
        false_positive_service=false_positive_service,
    )

    return service, client


def _seed_crop_less_detection(session: Session, *, label="sheep") -> int:
    asset = Asset(immich_asset_id="asset-1", extension=".jpg")
    detection = Detection(
        asset=asset,
        label=label,
        confidence=0.6,
        x1=10,
        y1=20,
        x2=110,
        y2=220,
    )
    session.add(detection)
    session.commit()

    return detection.id


def _open_upright_stub(monkeypatch):
    monkeypatch.setattr(
        "immich_dog_tagger.services.manual_detection_assignment.open_upright",
        lambda source: FakeImage(),
    )


def test_assign_creates_a_crop_and_names_an_identity(engine, tmp_path, monkeypatch):
    _open_upright_stub(monkeypatch)

    with Session(engine) as session:
        detection_id = _seed_crop_less_detection(session)

        service, client = _build_service(session, tmp_path)

        crop = service.assign(detection_id, Species.DOG, "Rex")

        assert crop.species == Species.DOG
        assert crop.detection_id == detection_id
        assert client.requested_asset_ids == ["asset-1"]

        classification = session.scalars(
            select(CropClassification).where(CropClassification.crop_id == crop.id)
        ).one()
        assert classification.identity == "Rex"
        assert classification.confidence == 1.0
        assert classification.source == ClassificationSources.REVIEW
        assert classification.embedding is not None

        action = session.scalars(
            select(ReviewAction).where(
                ReviewAction.classification_id == classification.id
            )
        ).one()
        assert action.action == ReviewActions.CORRECT
        assert action.original_identity is None
        assert action.identity == "Rex"


def test_assign_with_no_identity_lands_at_unknown(engine, tmp_path, monkeypatch):
    _open_upright_stub(monkeypatch)

    with Session(engine) as session:
        detection_id = _seed_crop_less_detection(session, label="person")

        service, _ = _build_service(session, tmp_path)

        crop = service.assign(detection_id, Species.DOG, None)

        classification = session.scalars(
            select(CropClassification).where(CropClassification.crop_id == crop.id)
        ).one()
        assert classification.identity is None
        assert classification.confidence == 1.0


def test_assign_rejects_a_detection_that_already_has_a_crop(engine, tmp_path):
    with Session(engine) as session:
        asset = Asset(immich_asset_id="asset-1", extension=".jpg")
        detection = Detection(
            asset=asset, label="dog", confidence=0.9, x1=0, y1=0, x2=10, y2=10
        )
        crop = Crop(detection=detection, path="crop.jpg", species=Species.DOG)
        session.add(crop)
        session.commit()

        service, _ = _build_service(session, tmp_path)

        with pytest.raises(ValueError, match="already has a crop"):
            service.assign(detection.id, Species.DOG, "Rex")


def test_assign_raises_for_unknown_detection(engine, tmp_path):
    with Session(engine) as session:
        service, _ = _build_service(session, tmp_path)

        with pytest.raises(ValueError, match="not found"):
            service.assign(999999, Species.DOG, "Rex")


def test_assign_raises_for_a_degenerate_box(engine, tmp_path, monkeypatch):
    _open_upright_stub(monkeypatch)

    with Session(engine) as session:
        detection_id = _seed_crop_less_detection(session)

        crop_writer = FakeCropWriter(tmp_path)
        crop_writer.degenerate = True

        service, _ = _build_service(session, tmp_path, crop_writer=crop_writer)

        with pytest.raises(ValueError, match="degenerate"):
            service.assign(detection_id, Species.DOG, "Rex")


def test_mark_not_animal_creates_a_crop_flagged_not_animal(
    engine, tmp_path, monkeypatch
):
    _open_upright_stub(monkeypatch)

    with Session(engine) as session:
        detection_id = _seed_crop_less_detection(session, label="sheep")

        service, _ = _build_service(session, tmp_path)

        crop = service.mark_not_animal(detection_id)

        assert crop.not_animal is True
        assert crop.classification is None


def test_mark_not_animal_rejects_a_detection_that_already_has_a_crop(engine, tmp_path):
    with Session(engine) as session:
        asset = Asset(immich_asset_id="asset-1", extension=".jpg")
        detection = Detection(
            asset=asset, label="dog", confidence=0.9, x1=0, y1=0, x2=10, y2=10
        )
        crop = Crop(detection=detection, path="crop.jpg", species=Species.DOG)
        session.add(crop)
        session.commit()

        service, _ = _build_service(session, tmp_path)

        with pytest.raises(ValueError, match="already has a crop"):
            service.mark_not_animal(detection.id)
