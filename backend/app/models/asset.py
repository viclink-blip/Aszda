"""Media assets. The bytes live in object storage; only metadata lives here."""

from __future__ import annotations

import enum
import uuid

from sqlalchemy import BigInteger, CheckConstraint, Enum, Float, ForeignKey, Index, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db
from app.models.base import Timestamps, UUIDPrimaryKey


class AssetKind(enum.StrEnum):
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    TEXT = "text"


class AssetSource(enum.StrEnum):
    UPLOAD = "upload"
    GENERATED = "generated"


class Asset(UUIDPrimaryKey, Timestamps, db.Model):
    __tablename__ = "assets"

    owner_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("projects.id", ondelete="CASCADE")
    )
    generation_job_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("generation_jobs.id", ondelete="SET NULL")
    )
    kind: Mapped[AssetKind] = mapped_column(
        Enum(AssetKind, name="asset_kind", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    source: Mapped[AssetSource] = mapped_column(
        Enum(AssetSource, name="asset_source", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    # Server-generated storage key; never derived from the user's file name.
    storage_key: Mapped[str] = mapped_column(String(512), unique=True, nullable=False)
    original_filename: Mapped[str | None] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    # For generated assets: which AI provider and model produced it.
    provider: Mapped[str | None] = mapped_column(String(50))
    model: Mapped[str | None] = mapped_column(String(100))

    __table_args__ = (
        Index("ix_assets_project_created", "project_id", "created_at"),
        Index("ix_assets_owner_created", "owner_id", "created_at"),
        Index("ix_assets_generation_job_id", "generation_job_id"),
        CheckConstraint("size_bytes >= 0", name="size_non_negative"),
    )
