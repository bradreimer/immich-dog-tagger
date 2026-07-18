"""
Database models.
"""

from datetime import datetime

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import func

class Base(DeclarativeBase):
    pass


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    immich_asset_id: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
    )

    checksum: Mapped[str | None] = mapped_column(
        String(128),
    )

    status: Mapped[str] = mapped_column(
        String(32),
        default="pending",
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )
    

class Detection(Base):
    __tablename__ = "detections"

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    asset_id: Mapped[int] = mapped_column(
        ForeignKey("assets.id"),
        nullable=False,
    )

    label: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    confidence: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    x1: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    y1: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    x2: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    y2: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
