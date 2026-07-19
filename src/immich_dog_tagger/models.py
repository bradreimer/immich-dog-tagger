"""
Database models.
"""

from datetime import datetime
from pathlib import Path
from .status import AssetStatus

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    LargeBinary,
    String,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func


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

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )

    identity: Mapped["Identity"] = relationship(back_populates="embeddings")


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
