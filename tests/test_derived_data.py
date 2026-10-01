"""Tests for derived-data detection and rebuild guidance."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from immich_dog_tagger.enums import ReviewActions
from immich_dog_tagger.models import (
    Asset,
    AssetStatus,
    Crop,
    CropClassification,
    Detection,
    EmbeddingExample,
    Identity,
    ReviewAction,
)
from immich_dog_tagger.services.derived_data import (
    DerivedDataReport,
    DerivedDataService,
    check_derived_data,
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
    identity = session.query(Identity).filter_by(name="Fido").one_or_none()
    if identity is None:
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
    assert report.orphaned_example_paths == [str(tmp_path / "missing_emb.jpg")]


def test_check_does_not_count_example_sharing_a_live_missing_crop_as_orphaned(
    session, tmp_path
):
    # The crop repair regenerates this file, so the example isn't orphaned.
    cache_dir = tmp_path / "cache"
    asset = _make_asset(session, status=AssetStatus.DETECTED)
    det = _make_detection(session, asset)
    path = str(tmp_path / "missing_crop.jpg")
    _make_crop(session, det, path)
    _make_example(session, path)
    session.commit()

    report = DerivedDataService(session, cache_dir).check()

    assert report.missing_embedding_sources == [path]
    assert report.orphaned_example_paths == []


def test_check_counts_example_of_a_removed_asset_crop_as_orphaned(session, tmp_path):
    # A removed photo's crop can't be regenerated either.
    asset = _make_asset(session, status=AssetStatus.REMOVED)
    det = _make_detection(session, asset)
    path = str(tmp_path / "gone.jpg")
    _make_crop(session, det, path)
    _make_example(session, path)
    session.commit()

    report = DerivedDataService(session, tmp_path / "cache").check()

    assert report.orphaned_example_paths == [path]


def test_rebuild_guidance_produced_for_each_category(tmp_path):
    report = DerivedDataReport(
        missing_downloads=["a"],
        missing_crops=["b"],
        missing_embedding_sources=["c"],
        orphaned_example_paths=["c"],
    )
    guidance = DerivedDataService.rebuild_guidance(report)
    combined = "\n".join(guidance)
    assert "download" in combined
    assert "detect" in combined
    assert "check-derived-data --repair" in combined
    # import-review only imports cache/review/confirmed/ -- it can't rebuild
    # these (issue #379).
    assert "import-review" not in combined


def test_report_as_dict_keys():
    report = DerivedDataReport()
    d = report.as_dict()
    assert {
        "healthy",
        "missing_downloads",
        "missing_crops",
        "missing_embedding_sources",
        "total_missing",
        "reviewed_at_risk",
        "orphaned_examples",
    } <= d.keys()


def test_check_excludes_crops_of_a_removed_asset(session, tmp_path):
    # Issue #194: a crop deliberately deleted as part of Immich-deletion
    # reconciliation is not "missing" -- it shouldn't show up as something
    # to repair forever.
    cache_dir = tmp_path / "cache"
    asset = _make_asset(session, status=AssetStatus.REMOVED)
    det = _make_detection(session, asset)
    _make_crop(session, det, str(tmp_path / "gone.jpg"))
    session.commit()

    svc = DerivedDataService(session, cache_dir)
    report = svc.check()

    assert report.missing_crops == []
    assert report.healthy


def test_repair_routes_missing_download_back_to_download_failed(session, tmp_path):
    cache_dir = tmp_path / "cache"
    asset = _make_asset(session)
    session.commit()

    svc = DerivedDataService(session, cache_dir)
    summary = svc.repair()

    assert summary.downloads_repaired == 1

    session.refresh(asset)
    assert asset.status is AssetStatus.DOWNLOAD_FAILED

    report = svc.check()
    assert report.missing_downloads == []


def test_repair_routes_missing_crop_back_to_downloaded_for_redetect(session, tmp_path):
    cache_dir = tmp_path / "cache"
    asset = _make_asset(session, status=AssetStatus.DETECTED)
    file = asset.cache_path(cache_dir)
    file.parent.mkdir(parents=True, exist_ok=True)
    file.touch()

    det = _make_detection(session, asset)
    _make_crop(session, det, str(tmp_path / "missing_crop.jpg"))
    session.commit()

    svc = DerivedDataService(session, cache_dir)
    summary = svc.repair()

    assert summary.crops_repaired == 1

    session.refresh(asset)
    assert asset.status is AssetStatus.DOWNLOADED
    assert session.query(Detection).filter_by(asset_id=asset.id).count() == 0
    assert session.query(Crop).count() == 0

    report = svc.check()
    assert report.missing_crops == []


def test_repair_removes_orphaned_example(session, tmp_path):
    # Issue #379: no Crop row (so no bounding box) remains to rebuild this
    # example's source from, so repair removes it.
    orphan = _make_example(session, str(tmp_path / "missing_emb.jpg"))
    orphan_id = orphan.id
    present_path = tmp_path / "present.jpg"
    present_path.touch()
    kept = _make_example(session, str(present_path))
    session.commit()

    svc = DerivedDataService(session, tmp_path / "cache")
    summary = svc.repair()

    assert summary.examples_removed == 1
    assert summary.total_repaired == 1
    assert session.get(EmbeddingExample, orphan_id) is None
    assert session.get(EmbeddingExample, kept.id) is not None

    report = svc.check()
    assert report.missing_embedding_sources == []
    assert report.healthy


def test_repair_clears_matched_example_on_classifications(session, tmp_path):
    orphan = _make_example(session, str(tmp_path / "missing_emb.jpg"))
    asset = _make_asset(session, status=AssetStatus.REMOVED)
    det = _make_detection(session, asset)
    crop = _make_crop(session, det, str(tmp_path / "other.jpg"))
    classification = CropClassification(
        crop_id=crop.id,
        identity="Fido",
        confidence=0.9,
        matched_example_id=orphan.id,
    )
    session.add(classification)
    session.commit()

    summary = DerivedDataService(session, tmp_path / "cache").repair()

    assert summary.examples_removed == 1
    session.refresh(classification)
    assert classification.matched_example_id is None


def test_repair_keeps_example_sharing_a_live_missing_crop(session, tmp_path):
    # The crop repair routes the asset back to detect, which regenerates the
    # file -- the example isn't orphaned, so it stays.
    cache_dir = tmp_path / "cache"
    asset = _make_asset(session, status=AssetStatus.DETECTED)
    file = asset.cache_path(cache_dir)
    file.parent.mkdir(parents=True, exist_ok=True)
    file.touch()
    det = _make_detection(session, asset)
    path = str(tmp_path / "missing_crop.jpg")
    _make_crop(session, det, path)
    example = _make_example(session, path)
    session.commit()

    summary = DerivedDataService(session, cache_dir).repair()

    assert summary.crops_repaired == 1
    assert summary.examples_removed == 0
    assert session.get(EmbeddingExample, example.id) is not None


def test_repair_keeps_another_crop_file_a_learned_example_uses(session, tmp_path):
    # Issue #380: repairing one missing crop re-detects the whole photo, so
    # its other crops are discarded -- one a learned example uses must move
    # aside rather than be deleted.
    cache_dir = tmp_path / "cache"
    asset = _make_asset(session, status=AssetStatus.DETECTED)
    file = asset.cache_path(cache_dir)
    file.parent.mkdir(parents=True, exist_ok=True)
    file.touch()
    _make_crop(session, _make_detection(session, asset), str(tmp_path / "missing.jpg"))
    learned = tmp_path / "learned.jpg"
    learned.write_bytes(b"learned crop")
    _make_crop(session, _make_detection(session, asset), str(learned))
    example = _make_example(session, str(learned))
    session.commit()

    summary = DerivedDataService(session, cache_dir).repair()

    assert summary.crops_repaired == 1
    assert summary.examples_removed == 0
    session.refresh(example)
    assert Path(example.crop_path).read_bytes() == b"learned crop"
    assert not learned.exists()


def test_repair_isolates_a_failed_example_removal(session, tmp_path, monkeypatch):
    first = _make_example(session, str(tmp_path / "a.jpg"))
    second = _make_example(session, str(tmp_path / "b.jpg"))
    first_id, second_id = first.id, second.id
    session.commit()

    original_delete = session.delete

    def flaky_delete(obj):
        if isinstance(obj, EmbeddingExample) and obj.id == first_id:
            raise RuntimeError("boom")
        original_delete(obj)

    monkeypatch.setattr(session, "delete", flaky_delete)

    summary = DerivedDataService(session, tmp_path / "cache").repair()

    assert summary.examples_removed == 1
    assert summary.failed == 1
    assert session.get(EmbeddingExample, first_id) is not None
    assert session.get(EmbeddingExample, second_id) is None


def test_check_derived_data_releases_session_before_scanning_disk(
    engine, tmp_path, monkeypatch
):
    """
    Issue #317: GET /diagnostics held its pooled session checked out for the whole
    derived-data filesystem scan, which under concurrent requests could exhaust the
    connection pool. check_derived_data() must query and release its own session
    before running the (potentially slow) per-file exists() checks.
    """
    cache_dir = tmp_path / "cache"
    with Session(engine) as session:
        _make_asset(session)
        session.commit()

    checked_out_during_scan: list[int] = []
    real_exists = Path.exists

    def spying_exists(self):
        checked_out_during_scan.append(engine.pool.checkedout())
        return real_exists(self)

    monkeypatch.setattr(Path, "exists", spying_exists)

    report = check_derived_data(engine, cache_dir)

    assert checked_out_during_scan, "the disk scan never ran"
    assert all(count == 0 for count in checked_out_during_scan), (
        "a DB connection was still checked out of the pool during the disk scan"
    )
    assert report.missing_downloads == ["asset-1"]


def test_check_reports_reviewed_at_risk_for_missing_crop(session, tmp_path):
    cache_dir = tmp_path / "cache"
    asset = _make_asset(session, status=AssetStatus.DETECTED)
    det = _make_detection(session, asset)
    crop = _make_crop(session, det, str(tmp_path / "missing_crop.jpg"))

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

    svc = DerivedDataService(session, cache_dir)
    report = svc.check()

    assert report.missing_crops == [crop.path]
    assert report.reviewed_at_risk == 1


def test_check_reports_zero_reviewed_at_risk_when_missing_crop_never_reviewed(
    session, tmp_path
):
    cache_dir = tmp_path / "cache"
    asset = _make_asset(session, status=AssetStatus.DETECTED)
    det = _make_detection(session, asset)
    _make_crop(session, det, str(tmp_path / "missing_crop.jpg"))
    session.commit()

    svc = DerivedDataService(session, cache_dir)
    report = svc.check()

    assert report.reviewed_at_risk == 0


def test_repair_isolates_a_failure_on_one_asset(session, tmp_path, monkeypatch):
    # Issue #323/FR-6: DerivedDataService.repair() must not let one asset's
    # failure abort the batch or leave an earlier, already-repaired asset's
    # changes uncommitted.
    cache_dir = tmp_path / "cache"
    good_asset = _make_asset(session, immich_id="good", status=AssetStatus.DETECTED)
    good_det = _make_detection(session, good_asset)
    _make_crop(session, good_det, str(tmp_path / "good_missing.jpg"))

    bad_asset = _make_asset(session, immich_id="bad", status=AssetStatus.DETECTED)
    bad_det = _make_detection(session, bad_asset)
    _make_crop(session, bad_det, str(tmp_path / "bad_missing.jpg"))
    session.commit()

    svc = DerivedDataService(session, cache_dir)

    original_get = session.get

    def flaky_get(model, ident, *args, **kwargs):
        obj = original_get(model, ident, *args, **kwargs)
        if model is Asset and obj is not None and obj.immich_asset_id == "bad":
            raise RuntimeError("boom")
        return obj

    monkeypatch.setattr(session, "get", flaky_get)

    summary = svc.repair()

    assert summary.crops_repaired == 1
    assert summary.failed == 1

    monkeypatch.setattr(session, "get", original_get)
    session.refresh(good_asset)
    session.refresh(bad_asset)

    assert good_asset.status is AssetStatus.DOWNLOADED
    assert session.query(Detection).filter_by(asset_id=good_asset.id).count() == 0

    # The failing asset is untouched -- its stale detection/crop are still there.
    assert bad_asset.status is AssetStatus.DETECTED
    assert session.query(Detection).filter_by(asset_id=bad_asset.id).count() == 1


def test_repair_isolates_a_failed_download_repair(session, tmp_path, monkeypatch):
    cache_dir = tmp_path / "cache"
    good_asset = _make_asset(session, immich_id="good")
    bad_asset = _make_asset(session, immich_id="bad")
    session.commit()

    svc = DerivedDataService(session, cache_dir)

    original_scalar = session.scalar

    def flaky_scalar(statement, *args, **kwargs):
        result = original_scalar(statement, *args, **kwargs)
        if isinstance(result, Asset) and result.immich_asset_id == "bad":
            raise RuntimeError("boom")
        return result

    monkeypatch.setattr(session, "scalar", flaky_scalar)

    summary = svc.repair()

    assert summary.downloads_repaired == 1
    assert summary.failed == 1

    monkeypatch.setattr(session, "scalar", original_scalar)
    session.refresh(good_asset)
    session.refresh(bad_asset)

    assert good_asset.status is AssetStatus.DOWNLOAD_FAILED
    assert bad_asset.status is AssetStatus.DOWNLOADED


def test_repair_prioritizes_download_when_both_original_and_crop_missing(
    session, tmp_path
):
    cache_dir = tmp_path / "cache"
    asset = _make_asset(session, status=AssetStatus.DOWNLOADED)
    det = _make_detection(session, asset)
    _make_crop(session, det, str(tmp_path / "missing_crop.jpg"))
    session.commit()

    svc = DerivedDataService(session, cache_dir)
    svc.repair()

    session.refresh(asset)

    # Original is also missing -- download must run before detect, so the
    # asset stays DOWNLOAD_FAILED rather than being sent straight back to
    # DOWNLOADED with no file to detect against.
    assert asset.status is AssetStatus.DOWNLOAD_FAILED
    assert session.query(Detection).filter_by(asset_id=asset.id).count() == 0
