"""
Database models.
"""

from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    LargeBinary,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from .enums import (
    AssetStatus,
    ClassificationPassStatus,
    ClassificationSources,
    EmbeddingSources,
    PipelineJobStatus,
    PipelineOperation,
    ReviewActions,
    Species,
)


class Base(DeclarativeBase):
    pass


class Identity(Base):
    __tablename__ = "identities"
    __table_args__ = (
        UniqueConstraint("species", "name", name="uq_identities_species_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    # Identity names are unique per species, not globally (DT-1110) -- a dog
    # "Max" and a cat "Max" are different identities and must not collide.
    species: Mapped[Species] = mapped_column(
        Enum(Species, native_enum=False),
        nullable=False,
        default=Species.DOG,
        server_default=Species.DOG.name,
    )

    name: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="1",
    )

    embeddings: Mapped[list[EmbeddingExample]] = relationship(
        back_populates="identity",
        cascade="all, delete-orphan",
    )


class EmbeddingExample(Base):
    __tablename__ = "embedding_examples"

    id: Mapped[int] = mapped_column(primary_key=True)

    identity_id: Mapped[int] = mapped_column(
        ForeignKey("identities.id"),
        index=True,
    )

    crop_path: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
    )

    embedding: Mapped[bytes] = mapped_column(
        LargeBinary,
        nullable=False,
    )

    source: Mapped[EmbeddingSources] = mapped_column(
        Enum(
            EmbeddingSources,
            native_enum=False,
        ),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )

    captured_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    identity: Mapped[Identity] = relationship(
        back_populates="embeddings",
    )

    matched_classifications: Mapped[list[CropClassification]] = relationship(
        back_populates="matched_example",
        foreign_keys="CropClassification.matched_example_id",
    )

    def __repr__(self) -> str:
        return (
            f"EmbeddingExample("
            f"id={self.id}, "
            f"identity={self.identity_id}, "
            f"source={self.source!r}, "
            f"path={self.crop_path!r})"
        )


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(primary_key=True)

    immich_asset_id: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
    )

    checksum: Mapped[str | None] = mapped_column(
        String(128),
    )

    extension: Mapped[str] = mapped_column(
        String(16),
    )

    status: Mapped[AssetStatus] = mapped_column(
        Enum(
            AssetStatus,
            native_enum=False,
        ),
        default=AssetStatus.PENDING,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )

    detections: Mapped[list[Detection]] = relationship(
        back_populates="asset",
        cascade="all, delete-orphan",
    )

    captured_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    def cache_path(
        self,
        cache_dir: Path,
    ) -> Path:
        return cache_dir / f"{self.immich_asset_id}{self.extension}"


class Detection(Base):
    __tablename__ = "detections"

    id: Mapped[int] = mapped_column(primary_key=True)

    asset_id: Mapped[int] = mapped_column(
        ForeignKey("assets.id"),
        index=True,
    )

    label: Mapped[str]

    confidence: Mapped[float]

    x1: Mapped[int]
    y1: Mapped[int]
    x2: Mapped[int]
    y2: Mapped[int]

    asset: Mapped[Asset] = relationship(back_populates="detections")

    crop: Mapped[Crop] = relationship(
        back_populates="detection",
        cascade="all, delete-orphan",
    )


class CropClassification(Base):
    __tablename__ = "crop_classifications"

    id: Mapped[int] = mapped_column(primary_key=True)

    crop_id: Mapped[int] = mapped_column(
        ForeignKey("crops.id"),
        index=True,
    )

    identity: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    confidence: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    candidates: Mapped[list[dict]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

    source: Mapped[ClassificationSources] = mapped_column(
        Enum(
            ClassificationSources,
            native_enum=False,
        ),
        nullable=False,
        default=ClassificationSources.AUTO,
    )

    classifier_version: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
    )

    classification_pass_id: Mapped[int | None] = mapped_column(
        ForeignKey("classification_passes.id"),
        nullable=True,
        index=True,
    )

    embedding: Mapped[bytes | None] = mapped_column(
        LargeBinary,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )

    crop: Mapped[Crop] = relationship(
        back_populates="classification",
    )

    classification_pass: Mapped[ClassificationPass | None] = relationship(
        back_populates="classifications",
    )

    matched_example_id: Mapped[int | None] = mapped_column(
        ForeignKey("embedding_examples.id"),
        nullable=True,
    )

    matched_example: Mapped[EmbeddingExample | None] = relationship(
        back_populates="matched_classifications",
        foreign_keys=[matched_example_id],
    )

    review_actions: Mapped[list[ReviewAction]] = relationship(
        cascade="all, delete-orphan",
    )


class ClassificationPass(Base):
    """
    A single Reclassify run: recomputes AUTO predictions from the current
    labeled-example set without touching reviewed/manual ground truth.
    """

    __tablename__ = "classification_passes"

    id: Mapped[int] = mapped_column(primary_key=True)

    status: Mapped[ClassificationPassStatus] = mapped_column(
        Enum(
            ClassificationPassStatus,
            native_enum=False,
        ),
        nullable=False,
        default=ClassificationPassStatus.RUNNING,
    )

    classifier_version: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    threshold: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    eligible_count: Mapped[int] = mapped_column(default=0, nullable=False)
    confident_count: Mapped[int] = mapped_column(default=0, nullable=False)
    needs_review_count: Mapped[int] = mapped_column(default=0, nullable=False)
    unknown_count: Mapped[int] = mapped_column(default=0, nullable=False)
    changed_count: Mapped[int] = mapped_column(default=0, nullable=False)

    # Snapshotted once the pass completes successfully; left null for passes
    # that predate this column or that failed mid-run (DT-1101). Not
    # backfillable -- a past queue/example-count state isn't reconstructable
    # from current data.
    labeled_example_count: Mapped[int | None] = mapped_column(nullable=True)
    review_queue_size: Mapped[int | None] = mapped_column(nullable=True)

    error_message: Mapped[str | None] = mapped_column(
        String(2048),
        nullable=True,
    )

    job_id: Mapped[int | None] = mapped_column(
        ForeignKey("pipeline_jobs.id"),
        nullable=True,
        index=True,
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    classifications: Mapped[list[CropClassification]] = relationship(
        back_populates="classification_pass",
    )


class Crop(Base):
    __tablename__ = "crops"

    id: Mapped[int] = mapped_column(primary_key=True)

    detection_id: Mapped[int] = mapped_column(
        ForeignKey("detections.id"),
        index=True,
    )

    path: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
    )

    # Set explicitly by DetectionService from the detection's COCO label at
    # crop-creation time (DT-1110). A real column, not a property computed
    # from crop.detection.label, so reading a crop's species never requires
    # its detection row to be loaded (or to exist at all, which many test
    # fixtures don't bother with) -- just this row.
    species: Mapped[Species] = mapped_column(
        Enum(Species, native_enum=False),
        nullable=False,
        default=Species.DOG,
        server_default=Species.DOG.name,
    )

    detection: Mapped[Detection] = relationship(back_populates="crop")

    classification: Mapped[CropClassification | None] = relationship(
        back_populates="crop",
        cascade="all, delete-orphan",
    )


class ReviewAction(Base):
    __tablename__ = "review_actions"

    id: Mapped[int] = mapped_column(primary_key=True)

    classification_id: Mapped[int] = mapped_column(
        ForeignKey("crop_classifications.id"),
        index=True,
    )

    action: Mapped[ReviewActions] = mapped_column(
        Enum(
            ReviewActions,
            native_enum=False,
        ),
        nullable=False,
    )

    identity: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    original_identity: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )


class PipelineSchedule(Base):
    __tablename__ = "pipeline_schedules"

    id: Mapped[int] = mapped_column(primary_key=True)

    name: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )

    operation: Mapped[PipelineOperation] = mapped_column(
        Enum(
            PipelineOperation,
            native_enum=False,
        ),
        nullable=False,
        index=True,
    )

    expression: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    timezone_name: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="UTC",
    )

    enabled: Mapped[bool] = mapped_column(
        default=True,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    next_run_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    last_run_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    last_run_result: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    jobs: Mapped[list[PipelineJob]] = relationship(
        back_populates="schedule",
        cascade="all, delete-orphan",
    )


class PipelineJob(Base):
    __tablename__ = "pipeline_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)

    operation: Mapped[PipelineOperation] = mapped_column(
        Enum(
            PipelineOperation,
            native_enum=False,
        ),
        nullable=False,
        index=True,
    )

    status: Mapped[PipelineJobStatus] = mapped_column(
        Enum(
            PipelineJobStatus,
            native_enum=False,
        ),
        nullable=False,
        default=PipelineJobStatus.PENDING,
        index=True,
    )

    progress_current: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
    )

    progress_total: Mapped[int | None] = mapped_column(
        nullable=True,
    )

    progress_message: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
    )

    error_message: Mapped[str | None] = mapped_column(
        String(2048),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    schedule_id: Mapped[int | None] = mapped_column(
        ForeignKey("pipeline_schedules.id"),
        nullable=True,
        index=True,
    )

    schedule: Mapped[PipelineSchedule | None] = relationship(
        back_populates="jobs",
    )

    def can_transition_to(
        self,
        next_status: PipelineJobStatus,
    ) -> bool:
        transitions = {
            PipelineJobStatus.PENDING: {
                PipelineJobStatus.RUNNING,
                PipelineJobStatus.CANCELED,
            },
            PipelineJobStatus.RUNNING: {
                PipelineJobStatus.COMPLETED,
                PipelineJobStatus.FAILED,
            },
            PipelineJobStatus.COMPLETED: set(),
            PipelineJobStatus.FAILED: set(),
            PipelineJobStatus.CANCELED: set(),
        }

        return next_status in transitions[self.status]

    def transition_to(
        self,
        next_status: PipelineJobStatus,
        *,
        now: datetime | None = None,
    ) -> None:
        if not self.can_transition_to(next_status):
            raise ValueError(
                f"Invalid pipeline job transition: {self.status.value} -> {next_status.value}"
            )

        timestamp = now or datetime.now(UTC).replace(tzinfo=None)

        self.status = next_status

        if next_status is PipelineJobStatus.RUNNING:
            self.started_at = timestamp

        if next_status in {
            PipelineJobStatus.COMPLETED,
            PipelineJobStatus.FAILED,
            PipelineJobStatus.CANCELED,
        }:
            self.completed_at = timestamp


class SyncedAsset(Base):
    """
    Tracks which (species, identity) album an Immich asset was synced into
    the last time SyncService.sync() ran (DT-1113). Diffing against this
    table -- rather than querying Immich's actual current album contents --
    is what lets sync() detect and undo a stale membership after a
    correction changes an asset's identity: per ADR-001, state.db is the
    source of truth, so this treats our own last-known-synced state as
    authoritative, not Immich's live state (which would also silently
    "fix" any manual album edits a user made directly in Immich).
    """

    __tablename__ = "synced_assets"

    id: Mapped[int] = mapped_column(primary_key=True)

    species: Mapped[Species] = mapped_column(
        Enum(Species, native_enum=False),
        nullable=False,
    )

    identity: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    immich_asset_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "species",
            "identity",
            "immich_asset_id",
            name="uq_synced_assets_species_identity_asset",
        ),
    )
