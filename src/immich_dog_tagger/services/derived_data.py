"""Detect missing derived artifacts and report rebuild guidance."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from immich_dog_tagger.models import (
    Asset,
    AssetStatus,
    Crop,
    Detection,
    EmbeddingExample,
)


@dataclass
class DerivedDataReport:
    missing_downloads: list[str] = field(default_factory=list)  # immich_asset_ids
    missing_crops: list[str] = field(default_factory=list)  # crop paths
    missing_embedding_sources: list[str] = field(default_factory=list)  # example paths

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
        }


@dataclass
class DerivedDataRepairSummary:
    downloads_repaired: int = 0
    crops_repaired: int = 0

    @property
    def total_repaired(self) -> int:
        return self.downloads_repaired + self.crops_repaired


def _load_check_candidates(
    session: Session, cache_dir: Path
) -> tuple[list[tuple[str, Path]], list[str], list[str]]:
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

    examples = session.scalars(select(EmbeddingExample)).all()
    example_paths = [example.crop_path for example in examples]

    return asset_paths, crop_paths, example_paths


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

    for path in example_paths:
        if not Path(path).exists():
            report.missing_embedding_sources.append(path)

    return report


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
        candidates = _load_check_candidates(session, cache_dir)

    return _scan_check_candidates(*candidates)


class DerivedDataService:
    def __init__(self, session: Session, cache_dir: Path) -> None:
        self.session = session
        self.cache_dir = cache_dir

    def check(self) -> DerivedDataReport:
        candidates = _load_check_candidates(self.session, self.cache_dir)
        return _scan_check_candidates(*candidates)

    def repair(self) -> DerivedDataRepairSummary:
        """
        Turn `check()`'s report into an actual fix (issue #194/FR-12):
        missing downloads and missing crops are automatically routed back
        through the pipeline. Missing embedding sources are left alone --
        there is nothing to regenerate them from; that still needs a human
        (re-run learn/import-review).
        """
        report = self.check()
        summary = DerivedDataRepairSummary()

        redownloading: set[str] = set()

        for immich_asset_id in report.missing_downloads:
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
            redownloading.add(immich_asset_id)
            summary.downloads_repaired += 1

        if report.missing_crops:
            missing_paths = set(report.missing_crops)
            crops = self.session.scalars(
                select(Crop).where(Crop.path.in_(missing_paths))
            ).all()

            affected_asset_ids = {
                crop.detection.asset_id for crop in crops if crop.detection is not None
            }

            for asset_id in affected_asset_ids:
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
                        crop_path = Path(detection.crop.path)

                        if crop_path.exists():
                            crop_path.unlink()

                    self.session.delete(detection)

                if asset.immich_asset_id not in redownloading:
                    # Original is fine -- send it straight back to
                    # DOWNLOADED so the next `detect` regenerates crops
                    # from scratch. If the original is also missing, it's
                    # already routed to DOWNLOAD_FAILED above; download
                    # runs before detect in the pipeline, so it'll reach
                    # detect again once that completes.
                    asset.status = AssetStatus.DOWNLOADED

                summary.crops_repaired += 1

        self.session.commit()

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
        if report.missing_embedding_sources:
            lines.append(
                f"# {len(report.missing_embedding_sources)} embedding source file(s) missing."
                " Re-run learn/import-review to rebuild embeddings:"
            )
            lines.append("  immich-dog-tagger import-review")
        return lines
