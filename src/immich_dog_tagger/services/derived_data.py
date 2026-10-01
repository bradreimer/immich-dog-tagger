"""Detect missing derived artifacts and report rebuild guidance."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from immich_dog_tagger.models import (
    Asset,
    AssetStatus,
    Crop,
    CropClassification,
    Detection,
    EmbeddingExample,
    ReviewAction,
)
from immich_dog_tagger.services.crop_files import discard_crop_file

logger = logging.getLogger(__name__)


@dataclass
class DerivedDataReport:
    missing_downloads: list[str] = field(default_factory=list)  # immich_asset_ids
    missing_crops: list[str] = field(default_factory=list)  # crop paths
    missing_embedding_sources: list[str] = field(default_factory=list)  # example paths
    # How many of the assets affected by missing_crops have recorded review
    # history that repair() would discard (issue #323/FR-2) -- repair()
    # deletes all of an affected asset's Detection rows, which cascades to
    # any CropClassification/ReviewAction tied to them.
    reviewed_at_risk: int = 0
    # The missing_embedding_sources that are orphaned (issue #379): no live
    # Crop row references the path, so the bounding box it was cut from is
    # gone and there is nothing to rebuild it from. repair() removes these.
    # The rest share a path with a missing crop and come back with it.
    orphaned_example_paths: list[str] = field(default_factory=list)

    @property
    def healthy(self) -> bool:
        return not (
            self.missing_downloads
            or self.missing_crops
            or self.missing_embedding_sources
        )

    @property
    def total_missing(self) -> int:
        return (
            len(self.missing_downloads)
            + len(self.missing_crops)
            + len(self.missing_embedding_sources)
        )

    def as_dict(self) -> dict:
        return {
            "healthy": self.healthy,
            "missing_downloads": len(self.missing_downloads),
            "missing_crops": len(self.missing_crops),
            "missing_embedding_sources": len(self.missing_embedding_sources),
            "total_missing": self.total_missing,
            "reviewed_at_risk": self.reviewed_at_risk,
            "orphaned_examples": len(self.orphaned_example_paths),
        }


@dataclass
class DerivedDataRepairSummary:
    downloads_repaired: int = 0
    crops_repaired: int = 0
    examples_removed: int = 0
    failed: int = 0

    @property
    def total_repaired(self) -> int:
        return self.downloads_repaired + self.crops_repaired + self.examples_removed


def _load_check_candidates(
    session: Session, cache_dir: Path
) -> tuple[list[tuple[str, Path]], list[str], list[str], dict[str, int]]:
    """
    Query the (asset id, path) / path lists `check()` verifies against disk. Split out
    from the scan itself so a caller can release the session before doing that scan
    (issue #317) -- see `check_derived_data` below.
    """
    assets = session.scalars(
        select(Asset).where(Asset.status == AssetStatus.DOWNLOADED)
    ).all()
    asset_paths = [
        (asset.immich_asset_id, asset.cache_path(cache_dir)) for asset in assets
    ]

    # Crops belonging to a reconciled-removed asset (issue #194) were
    # deliberately deleted, not lost -- excluded here so they don't show up
    # as something to repair forever.
    crops = session.scalars(
        select(Crop)
        .join(Detection, Crop.detection_id == Detection.id)
        .join(Asset, Detection.asset_id == Asset.id)
        .where(Asset.status != AssetStatus.REMOVED)
    ).all()
    crop_paths = [crop.path for crop in crops]
    # Maps a crop's path back to its asset id, so a caller that only learns
    # which paths are missing after the disk scan (see _scan_check_candidates)
    # can still tell which assets those missing crops belong to (issue #323).
    crop_path_to_asset_id = {
        crop.path: crop.detection.asset_id
        for crop in crops
        if crop.detection is not None
    }

    examples = session.scalars(select(EmbeddingExample)).all()
    example_paths = [example.crop_path for example in examples]

    return asset_paths, crop_paths, example_paths, crop_path_to_asset_id


def _scan_check_candidates(
    asset_paths: list[tuple[str, Path]],
    crop_paths: list[str],
    example_paths: list[str],
) -> DerivedDataReport:
    report = DerivedDataReport()

    for immich_asset_id, path in asset_paths:
        if not path.exists():
            report.missing_downloads.append(immich_asset_id)

    for path in crop_paths:
        if not Path(path).exists():
            report.missing_crops.append(path)

    live_crop_paths = set(crop_paths)

    for path in example_paths:
        if not Path(path).exists():
            report.missing_embedding_sources.append(path)

            if path not in live_crop_paths:
                report.orphaned_example_paths.append(path)

    return report


def _count_assets_with_review_history(session: Session, asset_ids: set[int]) -> int:
    """
    How many of `asset_ids` have at least one recorded ReviewAction --
    the review history repairing a missing crop would discard (issue #323/
    FR-2), mirroring StaleDetectionService._has_review_history's join shape.
    """
    if not asset_ids:
        return 0

    affected = session.scalars(
        select(Detection.asset_id)
        .join(Crop, Crop.detection_id == Detection.id)
        .join(CropClassification, CropClassification.crop_id == Crop.id)
        .join(ReviewAction, ReviewAction.classification_id == CropClassification.id)
        .where(Detection.asset_id.in_(asset_ids))
        .distinct()
    ).all()

    return len(affected)


def check_derived_data(engine: Engine, cache_dir: Path) -> DerivedDataReport:
    """
    Same check as `DerivedDataService.check()`, for a caller that must not hold its
    pooled DB session across the filesystem scan below. A large library can make that
    scan take seconds; holding a session checked out for the duration let concurrent
    requests (e.g. GET /diagnostics under UI polling) exhaust the connection pool
    (issue #317). Opens and closes its own short-lived session for the query only, same
    pattern as `get_viewable_crop_path` (issue #277).
    """
    with Session(engine) as session:
        asset_paths, crop_paths, example_paths, crop_path_to_asset_id = (
            _load_check_candidates(session, cache_dir)
        )

    report = _scan_check_candidates(asset_paths, crop_paths, example_paths)

    affected_asset_ids = {
        crop_path_to_asset_id[path]
        for path in report.missing_crops
        if path in crop_path_to_asset_id
    }

    if affected_asset_ids:
        # A second short-lived session (issue #317) -- this is a DB-only
        # lookup, not the slow per-file disk scan above, so it's fine to
        # check a session back out of the pool briefly for it.
        with Session(engine) as session:
            report.reviewed_at_risk = _count_assets_with_review_history(
                session, affected_asset_ids
            )

    return report


class DerivedDataService:
    def __init__(self, session: Session, cache_dir: Path) -> None:
        self.session = session
        self.cache_dir = cache_dir

    def check(self) -> DerivedDataReport:
        asset_paths, crop_paths, example_paths, crop_path_to_asset_id = (
            _load_check_candidates(self.session, self.cache_dir)
        )
        report = _scan_check_candidates(asset_paths, crop_paths, example_paths)

        affected_asset_ids = {
            crop_path_to_asset_id[path]
            for path in report.missing_crops
            if path in crop_path_to_asset_id
        }
        report.reviewed_at_risk = _count_assets_with_review_history(
            self.session, affected_asset_ids
        )

        return report

    def repair(self) -> DerivedDataRepairSummary:
        """
        Turn `check()`'s report into an actual fix (issue #194/FR-12):
        missing downloads and missing crops are automatically routed back
        through the pipeline. Orphaned embedding examples -- crop file gone and
        no live Crop row left to regenerate it from (issue #379) -- are
        removed: their bounding box was already discarded by an earlier
        re-detect/repair or their photo was removed, so they can never be
        re-embedded. An example whose path a live Crop row still references is
        left alone; the crop repair below regenerates that file.

        Each asset/example is committed (or rolled back) individually so one
        failure can't abort the rest of the batch or leave an earlier,
        already-repaired item's changes uncommitted (issue #323/FR-6).
        """
        report = self.check()
        summary = DerivedDataRepairSummary()

        redownloading: set[str] = set()

        for immich_asset_id in report.missing_downloads:
            try:
                asset = self.session.scalar(
                    select(Asset).where(Asset.immich_asset_id == immich_asset_id)
                )

                if asset is None or asset.status != AssetStatus.DOWNLOADED:
                    continue

                # Same routing DetectionService applies when it hits this itself
                # mid-run (FR-8): DOWNLOAD_FAILED is included in
                # Downloader.download_pending()'s default query, so the next
                # plain `download` re-fetches it.
                asset.status = AssetStatus.DOWNLOAD_FAILED
                self.session.commit()
                redownloading.add(immich_asset_id)
                summary.downloads_repaired += 1
            except Exception:
                self.session.rollback()
                logger.exception(
                    "Derived-data download repair failed for asset %s",
                    immich_asset_id,
                )
                summary.failed += 1

        if report.missing_crops:
            missing_paths = set(report.missing_crops)
            crops = self.session.scalars(
                select(Crop).where(Crop.path.in_(missing_paths))
            ).all()

            affected_asset_ids = {
                crop.detection.asset_id for crop in crops if crop.detection is not None
            }

            for asset_id in affected_asset_ids:
                try:
                    asset = self.session.get(Asset, asset_id)

                    if asset is None:
                        continue

                    # Stale Detection/Crop rows have to go regardless of
                    # whether the original is also missing -- detect's own
                    # query only reprocesses an asset with *no* Detection rows
                    # (mirrors what `detect --force` already does for a live
                    # re-detect).
                    detections = self.session.scalars(
                        select(Detection).where(Detection.asset_id == asset.id)
                    ).all()

                    for detection in detections:
                        if detection.crop is not None:
                            # Keeps a file a learned example still uses
                            # (issue #380).
                            discard_crop_file(self.session, detection.crop.path)

                        self.session.delete(detection)

                    if asset.immich_asset_id not in redownloading:
                        # Original is fine -- send it straight back to
                        # DOWNLOADED so the next `detect` regenerates crops
                        # from scratch. If the original is also missing, it's
                        # already routed to DOWNLOAD_FAILED above; download
                        # runs before detect in the pipeline, so it'll reach
                        # detect again once that completes.
                        asset.status = AssetStatus.DOWNLOADED

                    self.session.commit()
                    summary.crops_repaired += 1
                except Exception:
                    self.session.rollback()
                    logger.exception(
                        "Derived-data crop repair failed for asset id %s", asset_id
                    )
                    summary.failed += 1

        if report.orphaned_example_paths:
            examples = self.session.scalars(
                select(EmbeddingExample).where(
                    EmbeddingExample.crop_path.in_(set(report.orphaned_example_paths))
                )
            ).all()

            for example in examples:
                try:
                    if Path(example.crop_path).exists():
                        # Reappeared since check() -- no longer orphaned.
                        continue

                    self.session.delete(example)
                    self.session.commit()
                    summary.examples_removed += 1
                except Exception:
                    self.session.rollback()
                    logger.exception(
                        "Derived-data orphaned example removal failed for example id %s",
                        example.id,
                    )
                    summary.failed += 1

        return summary

    @staticmethod
    def rebuild_guidance(report: DerivedDataReport) -> list[str]:
        """Return CLI commands the user can run to rebuild missing artifacts."""
        lines: list[str] = []
        if report.missing_downloads:
            lines.append(
                f"# {len(report.missing_downloads)} downloaded asset file(s) missing."
                " Re-download with:"
            )
            lines.append("  immich-dog-tagger download")
        if report.missing_crops:
            lines.append(
                f"# {len(report.missing_crops)} crop file(s) missing."
                " Re-detect to rebuild crops:"
            )
            lines.append("  immich-dog-tagger detect")
        if report.orphaned_example_paths:
            # Not import-review: that only imports cache/review/confirmed/, so
            # it can't rebuild these (issue #379).
            lines.append(
                f"# {len(report.orphaned_example_paths)} learned example(s) have no source crop"
                " left to rebuild from. Remove them with:"
            )
            lines.append("  immich-dog-tagger check-derived-data --repair")
        return lines
