"""Tests for derived-data detection and rebuild guidance."""

from __future__ import annotations

from sqlalchemy.orm import Session

from immich_dog_tagger.models import (
    Asset,
    AssetStatus,
    Crop,
    Detection,
    EmbeddingExample,
    Identity,
)
from immich_dog_tagger.services.derived_data import (
    DerivedDataReport,
    DerivedDataService,
)


def _make_asset(
    session: Session, *, immich_id: str = "asset-1", status=AssetStatus.DOWNLOADED
) -> Asset:
    asset = Asset(
        immich_asset_id=immich_id,
        checksum="abc",
        extension=".jpg",
        status=status,
    )
    session.add(asset)
    session.flush()
    return asset


def _make_detection(session: Session, asset: Asset) -> Detection:
    det = Detection(
        asset_id=asset.id, label="dog", confidence=0.9, x1=0, y1=0, x2=10, y2=10
    )
    session.add(det)
    session.flush()
    return det


def _make_crop(session: Session, detection: Detection, path: str) -> Crop:
    crop = Crop(detection_id=detection.id, path=path)
    session.add(crop)
    session.flush()
    return crop


def _make_example(session: Session, path: str) -> EmbeddingExample:
    identity = Identity(name="Fido")
    session.add(identity)
    session.flush()
    example = EmbeddingExample(
        identity_id=identity.id,
        crop_path=path,
        embedding=b"\x00" * 4,
        source="bootstrap",
    )
    session.add(example)
    session.flush()
    return example


def test_report_healthy_when_all_files_present(session, tmp_path):
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    asset = _make_asset(session)
    file = asset.cache_path(cache_dir)
    file.parent.mkdir(parents=True, exist_ok=True)
    file.touch()

    det = _make_detection(session, asset)
    crop_path = tmp_path / "crop.jpg"
    crop_path.touch()
    _make_crop(session, det, str(crop_path))

    emb_path = tmp_path / "emb.jpg"
    emb_path.touch()
    _make_example(session, str(emb_path))
    session.commit()

    svc = DerivedDataService(session, cache_dir)
    report = svc.check()
    assert report.healthy


def test_report_ignores_missing_original_for_detected_asset(session, tmp_path):
    # Regression test for issue #93: detect deletes an asset's cached
    # original once its crops exist, moving the asset to DETECTED. The
    # health check must only require an original for DOWNLOADED assets --
    # a DETECTED asset with no cached original is the expected, healthy
    # end state, not a missing-download report.
    cache_dir = tmp_path / "cache"
    asset = _make_asset(session, status=AssetStatus.DETECTED)

    det = _make_detection(session, asset)
    crop_path = tmp_path / "crop.jpg"
    crop_path.touch()
    _make_crop(session, det, str(crop_path))
    session.commit()

    svc = DerivedDataService(session, cache_dir)
    report = svc.check()
    assert report.healthy
    assert report.missing_downloads == []


def test_report_detects_missing_download(session, tmp_path):
    cache_dir = tmp_path / "cache"
    _make_asset(session)
    session.commit()

    svc = DerivedDataService(session, cache_dir)
    report = svc.check()
    assert len(report.missing_downloads) == 1
    assert not report.healthy


def test_report_detects_missing_crop(session, tmp_path):
    cache_dir = tmp_path / "cache"
    asset = _make_asset(session)
    file = asset.cache_path(cache_dir)
    file.parent.mkdir(parents=True, exist_ok=True)
    file.touch()

    det = _make_detection(session, asset)
    _make_crop(session, det, str(tmp_path / "missing_crop.jpg"))
    session.commit()

    svc = DerivedDataService(session, cache_dir)
    report = svc.check()
    assert len(report.missing_crops) == 1


def test_report_detects_missing_embedding_source(session, tmp_path):
    _make_example(session, str(tmp_path / "missing_emb.jpg"))
    session.commit()

    svc = DerivedDataService(session, tmp_path / "cache")
    report = svc.check()
    assert len(report.missing_embedding_sources) == 1


def test_rebuild_guidance_produced_for_each_category(tmp_path):
    report = DerivedDataReport(
        missing_downloads=["a"],
        missing_crops=["b"],
        missing_embedding_sources=["c"],
    )
    guidance = DerivedDataService.rebuild_guidance(report)
    combined = "\n".join(guidance)
    assert "download" in combined
    assert "detect" in combined
    assert "import-review" in combined


def test_report_as_dict_keys():
    report = DerivedDataReport()
    d = report.as_dict()
    assert {
        "healthy",
        "missing_downloads",
        "missing_crops",
        "missing_embedding_sources",
        "total_missing",
    } <= d.keys()
