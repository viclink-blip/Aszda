"""Projects and the structured story data inside them (characters, scenes).

Scenes carry their own storyboard fields (position, shot notes) instead of a
separate Storyboard table: a project has exactly one storyboard, which is simply
its scenes in order. A separate table can be introduced if multiple storyboard
versions per project become a requirement.
"""

from __future__ import annotations

import enum
import uuid

from sqlalchemy import (
    CheckConstraint,
    Column,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db
from app.models.base import Timestamps, UUIDPrimaryKey


class ProjectStatus(enum.StrEnum):
    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class Project(UUIDPrimaryKey, Timestamps, db.Model):
    __tablename__ = "projects"

    owner_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[ProjectStatus] = mapped_column(
        Enum(ProjectStatus, name="project_status", values_callable=lambda e: [m.value for m in e]),
        nullable=False, default=ProjectStatus.DRAFT,
    )
    # Free-form creative brief (genre, tone, audience...). Kept as JSON so the
    # future AI Film Director can extend it without schema changes.
    brief: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    characters: Mapped[list[Character]] = relationship(
        back_populates="project", cascade="all, delete-orphan", passive_deletes=True,
        order_by="Character.created_at",
    )
    scenes: Mapped[list[Scene]] = relationship(
        back_populates="project", cascade="all, delete-orphan", passive_deletes=True,
        order_by="Scene.position",
    )

    __table_args__ = (Index("ix_projects_owner_updated", "owner_id", "updated_at"),)


scene_characters = Table(
    "scene_characters",
    db.metadata,
    Column("scene_id", Uuid, ForeignKey("scenes.id", ondelete="CASCADE"), primary_key=True),
    Column("character_id", Uuid, ForeignKey("characters.id", ondelete="CASCADE"), primary_key=True),
)


class Character(UUIDPrimaryKey, Timestamps, db.Model):
    __tablename__ = "characters"

    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # Structured traits (appearance, personality, voice...) for future AI use.
    traits: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    reference_asset_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("assets.id", ondelete="SET NULL", use_alter=True,
                         name="fk_characters_reference_asset_id_assets")
    )

    project: Mapped[Project] = relationship(back_populates="characters")


class Scene(UUIDPrimaryKey, Timestamps, db.Model):
    __tablename__ = "scenes"

    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # Storyboard fields
    shot_notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    dialogue: Mapped[str] = mapped_column(Text, nullable=False, default="")
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    preview_asset_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("assets.id", ondelete="SET NULL", use_alter=True,
                         name="fk_scenes_preview_asset_id_assets")
    )

    project: Mapped[Project] = relationship(back_populates="scenes")
    characters: Mapped[list[Character]] = relationship(secondary=scene_characters)

    __table_args__ = (
        # Deferrable so a reorder can swap positions inside one transaction.
        UniqueConstraint("project_id", "position", name="uq_scenes_project_position",
                         deferrable=True, initially="DEFERRED"),
        CheckConstraint("position >= 0", name="position_non_negative"),
        CheckConstraint("duration_seconds IS NULL OR duration_seconds > 0",
                        name="duration_positive"),
    )
