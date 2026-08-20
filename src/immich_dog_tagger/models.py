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


class IdentityMerge(Base):
    """
    Provenance for a merge of one identity into another (issue #148).

    A merge is a bulk re-attribution of derived state -- every classification
    and reference example the source owned moves to the target -- so unlike a
    rename it cannot be read back off the rows it touched. state.db holds
    history that cannot be regenerated (ADR-001), so the merge itself is
    recorded here: who absorbed whom, under which species, and how much moved.
    Names are denormalized alongside the foreign keys because the target can
    be renamed afterwards and the source is only a deactivated tombstone.
    """

    __tablename__ = "identity_merges"

    id: Mapped[int] = mapped_column(primary_key=True)

    source_identity_id: Mapped[int] = mapped_column(
        ForeignKey("identities.id"),
        nullable=False,
        index=True,
    )

    target_identity_id: Mapped[int] = mapped_column(
        ForeignKey("identities.id"),
        nullable=False,
        index=True,
    )

    source_name: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    target_name: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    species: Mapped[Species] = mapped_column(
        Enum(Species, native_enum=False),
        nullable=False,
    )

    classifications_reassigned: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
    )

    examples_reassigned: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
    )

    examples_discarded: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
    )

    occurrences_reassigned: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"IdentityMerge("
            f"id={self.id}, "
            f"source={self.source_name!r}, "
            f"target={self.target_name!r}, "
            f"species={self.species!r})"
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

    # Cached from Immich's own exifInfo/people/isFavorite (issue #94) -- read
    # from the same /api/search/metadata response the scanner already
    # fetches, never a separate Dog Tagger-side computation. Genuinely absent
    # for photos with no GPS/location data, not "not yet synced".
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    country: Mapped[str | None] = mapped_column(String(128), nullable=True)
    state: Mapped[str | None] = mapped_column(String(128), nullable=True)
    city: Mapped[str | None] = mapped_column(String(128), nullable=True)

    is_favorite: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="0",
    )

    # Immich-recognized people on this asset, cached as [{"id": ..., "name": ...}].
    # Not Dog Tagger's own face recognition -- a read-only cache of what
    # Immich already computed.
    people: Mapped[list[dict]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

    metadata_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    pet_occurrences: Mapped[list[PetOccurrence]] = relationship(
        back_populates="asset",
        cascade="all, delete-orphan",
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


class PetOccurrence(Base):
    """
    A settled fact: this identity was confirmed in this asset (issue #94).

    Materialized by PetOccurrenceService as a side effect of a
    CropClassification's identity being settled by AUTO classification,
    review correction, or reclassification -- never written directly by an
    API/UI action, and never itself the input to a further conclusion (see
    ADR-004). One row per crop_classification_id: a classification cleared
    to None/"Unknown" has no row, and a corrected/reclassified identity
    replaces rather than duplicates the row.
    """

    __tablename__ = "pet_occurrences"

    id: Mapped[int] = mapped_column(primary_key=True)

    crop_classification_id: Mapped[int] = mapped_column(
        ForeignKey("crop_classifications.id"),
        unique=True,
        nullable=False,
        index=True,
    )

    asset_id: Mapped[int] = mapped_column(
        ForeignKey("assets.id"),
        nullable=False,
        index=True,
    )

    identity_id: Mapped[int] = mapped_column(
        ForeignKey("identities.id"),
        nullable=False,
        index=True,
    )

    confidence: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    source: Mapped[ClassificationSources] = mapped_column(
        Enum(
            ClassificationSources,
            native_enum=False,
        ),
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

    classification: Mapped[CropClassification] = relationship()

    asset: Mapped[Asset] = relationship(back_populates="pet_occurrences")

    identity: Mapped[Identity] = relationship()


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


class CropIdentityRejection(Base):
    """
    A human saying "this crop is not <identity>" without saying who it is
    (issue #144).

    Deliberately its own table rather than a new `ReviewActions` value.
    `review_queue_count()`, `_has_review_action()`, the library's `reviewed`
    flag and the Metrics reviewed counts all derive from the mere
    *existence* of a `ReviewAction` row, so filing a rejection there would
    make a rejected crop count as reviewed everywhere at once -- while its
    identity is still unsettled and it still needs a human. That is the
    failure DT-1115 hit (one queue count meaning two different things) and
    the reason #116's species correction writes no `ReviewAction` either.

    Keyed on the crop, not the classification: the statement is about what
    the photo depicts, which is the crop's property, and it stays true if
    the classification is later rescored.
    """

    __tablename__ = "crop_identity_rejections"

    __table_args__ = (
        # One rejection per (crop, identity). Rejecting twice is the same
        # fact stated twice, not two facts.
        UniqueConstraint(
            "crop_id",
            "identity",
            name="uq_crop_identity_rejection",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    crop_id: Mapped[int] = mapped_column(
        ForeignKey("crops.id"),
        index=True,
    )

    identity: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )


class ManualAssetTag(Base):
    """
    "This photo contains <pet>", for a photo the detector found nothing in
    (issue #147).

    Without this, a pet YOLO missed -- small in frame, turned away, partly
    hidden -- is invisible to the entire system: no crop, so no
    classification, so it never reaches Review, the Library, or an Immich
    album, permanently and with no signal that it happened. Recall is
    silently capped by the detector.

    Deliberately a light fact about the *asset* rather than a manufactured
    Detection/Crop/CropClassification chain:

    - There is no crop file and no embedding, so a synthetic chain would
      have to invent both. `Learner` would then either reject it or, worse,
      learn from a whole-photo image as though it were a pet crop.
    - A pipeline re-run with `--force` recreates detections, crops and
      classifications with new ids, so anything hung off that chain would
      be destroyed by the next reprocess. An `Asset` is stable across
      reprocessing -- it is keyed by `immich_asset_id` -- so a tag hung
      here survives.

    Consequently this is read by sync (so the photo reaches the pet's
    album) and by nothing else: the classifier ignores it, and it never
    becomes a reference example. It records what the owner knows, without
    pretending to be evidence the model can learn from.
    """

    __tablename__ = "manual_asset_tags"

    __table_args__ = (
        UniqueConstraint(
            "asset_id",
            "species",
            "identity",
            name="uq_manual_asset_tag",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    asset_id: Mapped[int] = mapped_column(
        ForeignKey("assets.id"),
        index=True,
    )

    identity: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    species: Mapped[Species] = mapped_column(
        Enum(
            Species,
            native_enum=False,
        ),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )

    asset: Mapped[Asset] = relationship()


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

    # Liveness signal for an active job (issue #134): stamped when the job
    # starts and refreshed every time its own execution reports progress.
    # started_at alone can't tell a job that is working from one whose
    # process died mid-run, which is why Overview used to report every
    # RUNNING/PENDING job as "stuck" the moment it was started.
    heartbeat_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    schedule_id: Mapped[int | None] = mapped_column(
        ForeignKey("pipeline_schedules.id"),
        nullable=True,
        index=True,
    )

    # "Clear list" in the Job Queue UI (DT-1116) sets this False for
    # finished jobs rather than deleting the row -- the job history itself
    # is never lost, only hidden from list_recent()'s default result set.
    visible: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="1",
    )

    # Set by cancel_job() while this job is RUNNING (issue #111) -- status
    # deliberately stays RUNNING rather than moving to a separate
    # "canceling" state, so has_running_job()/the dispatcher/the scheduler
    # (all of which key off RUNNING) need no changes. The job's own
    # execution loop polls this flag at its existing batch-commit
    # checkpoints and transitions itself to CANCELED once it honors it.
    cancel_requested: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="0",
    )

    schedule: Mapped[PipelineSchedule | None] = relationship(
        back_populates="jobs",
    )

    @property
    def last_activity_at(self) -> datetime:
        """
        Most recent evidence this job was alive. Falls back through
        started_at to created_at so jobs written before heartbeats existed
        (and PENDING jobs, which have never run) still have a usable age.
        """

        return self.heartbeat_at or self.started_at or self.created_at

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
                PipelineJobStatus.CANCELED,
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
            self.heartbeat_at = timestamp

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
