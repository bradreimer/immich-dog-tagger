"""Tests for stale (EXIF-orientation) detection detection and batch repair."""

from __future__ import annotations

from unittest.mock import Mock

import numpy as np
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
from immich_dog_tagger.services.stale_detection import StaleDetectionService


def _make_asset(
    session: Session,
    *,
    immich_id: str = "asset-1",
    exif_width: int | None = 4032,
    exif_height: int | None = 3024,
    exif_orientation: int | None = 6,
) -> Asset:
    asset = Asset(
        immich_asset_id=immich_id,
        checksum="abc",
        extension=".jpg",
        status=AssetStatus.DETECTED,
        exif_width=exif_width,
        exif_height=exif_height,
        exif_orientation=exif_orientation,
    )
    session.add(asset)
    session.flush()
    return asset


def _make_detection(session: Session, asset: Asset, *, x2: int, y2: int) -> Detection:
    det = Detection(
        asset_id=asset.id, label="dog", confidence=0.9, x1=0, y1=0, x2=x2, y2=y2
    )
    session.add(det)
    session.flush()
    return det


def test_check_flags_box_outside_upright_but_inside_raw_bounds(session):
    # Raw (pre-rotation) dims 4032x3024; orientation 6 (90deg) swaps them to
    # an upright 3024x4032. x2=3500 exceeds the upright width (3024) but
    # still fits the raw width (4032) -- the geometric signature of a box
    # computed before the rotation fix.
    asset = _make_asset(session)
    _make_detection(session, asset, x2=3500, y2=100)
    session.commit()

    report = StaleDetectionService(session).check()

    assert report.flagged_immich_asset_ids == ["asset-1"]
    assert not report.healthy


def test_check_does_not_flag_box_that_fits_upright_bounds(session):
    asset = _make_asset(session)
    # Upright bounds are 3024x4032 -- this box fits comfortably.
    _make_detection(session, asset, x2=500, y2=500)
    session.commit()

    report = StaleDetectionService(session).check()

    assert report.flagged_immich_asset_ids == []
    assert report.healthy


def test_check_ignores_non_rotating_orientation(session):
    # Orientation 3 (180deg) doesn't swap width/height, so it's out of
    # reach for this geometric check (documented Non-goal) even with an
    # out-of-bounds-looking box.
    asset = _make_asset(session, exif_orientation=3)
    _make_detection(session, asset, x2=3500, y2=100)
    session.commit()

    report = StaleDetectionService(session).check()

    assert report.flagged_immich_asset_ids == []


def test_check_ignores_asset_with_no_exif_dimensions(session):
    asset = _make_asset(session, exif_width=None, exif_height=None)
    _make_detection(session, asset, x2=3500, y2=100)
    session.commit()

    report = StaleDetectionService(session).check()

    assert report.flagged_immich_asset_ids == []


def test_check_reports_reviewed_at_risk_count(session):
    asset = _make_asset(session)
    detection = _make_detection(session, asset, x2=3500, y2=100)
    crop = Crop(detection_id=detection.id, path="crop.jpg")
    session.add(crop)
    session.flush()

    classification = CropClassification(crop_id=crop.id, identity="Rex", confidence=0.8)
    session.add(classification)
    session.flush()

    session.add(
        ReviewAction(
            classification_id=classification.id,
            action=ReviewActions.CORRECT,
            identity="Rex",
        )
    )
    session.commit()

    report = StaleDetectionService(session).check()

    assert report.flagged_immich_asset_ids == ["asset-1"]
    assert report.reviewed_immich_asset_ids == ["asset-1"]
    assert report.reviewed_at_risk == 1


def test_report_as_dict_keys():
    from immich_dog_tagger.services.stale_detection import StaleDetectionReport

    report = StaleDetectionReport()
    d = report.as_dict()
    assert {"healthy", "flagged", "reviewed_at_risk"} <= d.keys()


class FakeDetector:
    def detect(self, image_path):
        return [
            DetectionResult(label="dog", confidence=0.99, x1=10, y1=20, x2=100, y2=200)
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
        return np.zeros((len(paths), 3), dtype=np.float32)


def _build_repair_service(session, tmp_path):
    client = Mock()
    client.download_asset.return_value = b"image data"

    classifier = Mock()
    classifier.classify.return_value = ClassificationResult(
        identity="Hermann",
        similarity=0.95,
        matched_example_id=None,
        candidates=[],
    )

    return AssetRepairService(
        session,
        Downloader(client, session, tmp_path),
        DetectionService(
            FakeDetector(), session, tmp_path, crop_writer=FakeCropWriter(tmp_path)
        ),
        ClassificationService(session, FakeBatchEmbedder(), classifier),
    )


def test_repair_skips_reviewed_assets_by_default(session, tmp_path):
    asset = _make_asset(session)
    detection = _make_detection(session, asset, x2=3500, y2=100)
    crop = Crop(detection_id=detection.id, path=str(tmp_path / "crop.jpg"))
    session.add(crop)
    session.flush()

    classification = CropClassification(crop_id=crop.id, identity="Rex", confidence=0.8)
    session.add(classification)
    session.flush()

    session.add(
        ReviewAction(
            classification_id=classification.id,
            action=ReviewActions.CORRECT,
            identity="Rex",
        )
    )
    session.commit()

    asset_repair_service = _build_repair_service(session, tmp_path)

    summary = StaleDetectionService(session).repair(asset_repair_service)

    assert summary.repaired == 0
    assert summary.skipped_reviewed == 1
    assert summary.failed == 0

    # Untouched: the original stale detection is still there.
    remaining = session.query(Detection).filter_by(asset_id=asset.id).one()
    assert remaining.id == detection.id


def test_repair_includes_reviewed_assets_when_opted_in(session, tmp_path):
    asset = _make_asset(session)
    detection = _make_detection(session, asset, x2=3500, y2=100)
    crop = Crop(detection_id=detection.id, path=str(tmp_path / "crop.jpg"))
    session.add(crop)
    session.flush()

    classification = CropClassification(crop_id=crop.id, identity="Rex", confidence=0.8)
    session.add(classification)
    session.flush()

    session.add(
        ReviewAction(
            classification_id=classification.id,
            action=ReviewActions.CORRECT,
            identity="Rex",
        )
    )
    session.commit()

    asset_repair_service = _build_repair_service(session, tmp_path)

    summary = StaleDetectionService(session).repair(
        asset_repair_service, include_reviewed=True
    )

    assert summary.repaired == 1
    assert summary.skipped_reviewed == 0
    assert session.query(ReviewAction).count() == 0


def test_repair_isolates_a_failure_on_one_asset(session, tmp_path):
    good_asset = _make_asset(session, immich_id="good")
    _make_detection(session, good_asset, x2=3500, y2=100)

    bad_asset = _make_asset(session, immich_id="bad")
    _make_detection(session, bad_asset, x2=3500, y2=100)
    session.commit()

    asset_repair_service = _build_repair_service(session, tmp_path)
    original_repair = asset_repair_service.repair

    def flaky_repair(immich_asset_id):
        if immich_asset_id == "bad":
            raise RuntimeError("boom")
        return original_repair(immich_asset_id)

    asset_repair_service.repair = flaky_repair

    summary = StaleDetectionService(session).repair(asset_repair_service)

    assert summary.repaired == 1
    assert summary.failed == 1


def test_repair_raises_nothing_when_nothing_flagged(session, tmp_path):
    asset_repair_service = _build_repair_service(session, tmp_path)

    summary = StaleDetectionService(session).repair(asset_repair_service)

    assert summary.total == 0
