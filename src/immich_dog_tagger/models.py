"""
Database models.
"""

from datetime import datetime
from enum import StrEnum
from pathlib import Path
from .status import AssetStatus

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Float,
    LargeBinary,
    String,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func


class EmbeddingSources(StrEnum):
    BOOTSTRAP = "bootstrap"
    REVIEW = "review"
    IMPORT = "import"


class Base(DeclarativeBase):
    pass


class Identity(Base):
    __tablename__ = "identities"

    id: Mapped[int] = mapped_column(primary_key=True)

    name: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
    )

    embeddings: Mapped[list["EmbeddingExample"]] = relationship(
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
        String(64),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )

    identity: Mapped["Identity"] = relationship(
        back_populates="embeddings",
    )

    matched_classifications: Mapped[list["CropClassification"]] = relationship(
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

    detections: Mapped[list["Detection"]] = relationship(
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

    asset: Mapped["Asset"] = relationship(back_populates="detections")

    crop: Mapped["Crop"] = relationship(
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

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )

    crop: Mapped["Crop"] = relationship(
        back_populates="classification",
    )

    matched_example_id: Mapped[int | None] = mapped_column(
        ForeignKey("embedding_examples.id"),
        nullable=True,
    )

    matched_example: Mapped["EmbeddingExample | None"] = relationship(
        back_populates="matched_classifications",
        foreign_keys=[matched_example_id],
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

    detection: Mapped["Detection"] = relationship(back_populates="crop")

    classification: Mapped["CropClassification | None"] = relationship(
        back_populates="crop",
        cascade="all, delete-orphan",
    )
