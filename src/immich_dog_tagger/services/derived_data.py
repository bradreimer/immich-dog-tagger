"""Detect missing derived artifacts and report rebuild guidance."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from immich_dog_tagger.models import Asset, AssetStatus, Crop, EmbeddingExample


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


class DerivedDataService:
    def __init__(self, session: Session, cache_dir: Path) -> None:
        self.session = session
        self.cache_dir = cache_dir

    def check(self) -> DerivedDataReport:
        report = DerivedDataReport()

        # Check downloaded asset files
        assets = self.session.scalars(
            select(Asset).where(Asset.status == AssetStatus.DOWNLOADED)
        ).all()
        for asset in assets:
            path = asset.cache_path(self.cache_dir)
            if not path.exists():
                report.missing_downloads.append(asset.immich_asset_id)

        # Check crop files
        crops = self.session.scalars(select(Crop)).all()
        for crop in crops:
            if not Path(crop.path).exists():
                report.missing_crops.append(crop.path)

        # Check embedding example source files
        examples = self.session.scalars(select(EmbeddingExample)).all()
        for example in examples:
            if not Path(example.crop_path).exists():
                report.missing_embedding_sources.append(example.crop_path)

        return report

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
