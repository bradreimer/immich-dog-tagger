from unittest.mock import Mock

import numpy as np
import pytest
from sqlalchemy.orm import Session

from immich_dog_tagger.classifier import ClassificationResult
from immich_dog_tagger.detector import DetectionResult
from immich_dog_tagger.downloader import Downloader
from immich_dog_tagger.enums import AssetStatus, ReviewActions
from immich_dog_tagger.models import (
    Asset,
    Crop,
    CropClassification,
    Detection,
    ReviewAction,
)
from immich_dog_tagger.services.asset_repair import AssetRepairService
from immich_dog_tagger.services.classification import ClassificationService
from immich_dog_tagger.services.detection import DetectionService


class FakeDetector:
    def detect(self, image_path):
        return [
            DetectionResult(
                label="dog",
                confidence=0.99,
                x1=10,
                y1=20,
                x2=100,
                y2=200,
            )
        ]


class FakeCropWriter:
    def __init__(self, tmp_path):
        self.tmp_path = tmp_path

    def write(self, image_path, asset_id, detections):
        results = []

        for index, _ in enumerate(detections):
            crop_path = self.tmp_path / f"{asset_id}_{index}.jpg"
            crop_path.write_bytes(b"crop")
            results.append((index, crop_path))

        return results


class FakeBatchEmbedder:
    def embed_batch(self, paths):
        return np.zeros(
            (len(paths), 3),
            dtype=np.float32,
        )


def _build_service(session, tmp_path):
    client = Mock()
    client.download_asset.return_value = b"image data"

    classifier = Mock()
    classifier.classify.return_value = ClassificationResult(
        identity="Hermann",
        similarity=0.95,
        matched_example_id=None,
        candidates=[],
    )

    service = AssetRepairService(
        session,
        Downloader(client, session, tmp_path),
        DetectionService(
            FakeDetector(),
            session,
            tmp_path,
            crop_writer=FakeCropWriter(tmp_path),
        ),
        ClassificationService(
            session,
            FakeBatchEmbedder(),
            classifier,
        ),
    )

    return service, client


def test_repair_replaces_detection_crop_and_classification(engine, tmp_path):
    # Regression coverage for issue #226: a photo processed before the
    # EXIF-orientation fix (#137) has stale Detection coordinates -- Repair
    # forces it back through download/detect/classify so the stored data
    # matches today's decode, discarding whatever review history was
    # recorded against the old rows (see AssetRepairService's docstring).
    with Session(engine) as session:
        asset = Asset(
            immich_asset_id="target",
            checksum="xyz",
            extension=".jpg",
            status=AssetStatus.DETECTED,
        )
        session.add(asset)
        session.commit()

        old_detection = Detection(
            asset=asset,
            label="dog",
            confidence=0.5,
            x1=0,
            y1=0,
            x2=10,
            y2=10,
        )
        old_crop = Crop(
            detection=old_detection,
            path=str(tmp_path / "old.jpg"),
        )
        session.add(old_crop)
        session.flush()

        old_classification = CropClassification(
            crop=old_crop,
            identity="Rex",
            confidence=0.8,
        )
        session.add(old_classification)
        session.flush()

        session.add(
            ReviewAction(
                classification_id=old_classification.id,
                action=ReviewActions.CORRECT,
                identity="Rex",
            )
        )
        session.commit()

        service, client = _build_service(session, tmp_path)

        result = service.repair("target")

        assert result.detections == 1
        assert result.dogs == 1
        assert result.cats == 0
        assert result.classified == 1
        assert result.status == AssetStatus.DETECTED
        client.download_asset.assert_called_once_with("target")

        # The old Detection/Crop/CropClassification/ReviewAction rows are
        # replaced (cascaded via the chain configured in models.py) rather
        # than kept alongside a new set: exactly one Detection/
        # CropClassification remain for this asset, carrying the freshly
        # classified identity rather than the old reviewed one, and the old
        # ReviewAction is gone with it. (Not asserted by comparing row ids:
        # SQLite can reuse a deleted row's rowid for the replacement.)
        assert session.query(ReviewAction).count() == 0

        detections = session.query(Detection).filter_by(asset_id=asset.id).all()
        assert len(detections) == 1

        new_classification = session.query(CropClassification).one()
        assert new_classification.identity == "Hermann"


def test_repair_does_not_touch_other_assets(engine, tmp_path):
    with Session(engine) as session:
        target = Asset(
            immich_asset_id="target",
            checksum="a",
            extension=".jpg",
            status=AssetStatus.DETECTED,
        )
        other = Asset(
            immich_asset_id="other",
            checksum="b",
            extension=".jpg",
            status=AssetStatus.DETECTED,
        )
        session.add_all([target, other])
        session.commit()

        other_detection = Detection(
            asset=other,
            label="dog",
            confidence=0.5,
            x1=0,
            y1=0,
            x2=10,
            y2=10,
        )
        other_crop = Crop(
            detection=other_detection,
            path=str(tmp_path / "other.jpg"),
        )
        session.add(other_crop)
        session.flush()

        other_classification = CropClassification(
            crop=other_crop,
            identity="Fido",
            confidence=0.9,
        )
        session.add(other_classification)
        session.commit()

        other_detection_id = other_detection.id
        other_classification_id = other_classification.id

        service, _ = _build_service(session, tmp_path)

        service.repair("target")

        assert session.get(Detection, other_detection_id) is not None
        assert session.get(CropClassification, other_classification_id) is not None


def test_repair_raises_for_unknown_asset(engine, tmp_path):
    with Session(engine) as session:
        service, _ = _build_service(session, tmp_path)

        with pytest.raises(ValueError):
            service.repair("does-not-exist")
