"""An automatic film: the AI Film Director plans a story, then every scene's image, video and
voice are generated and joined into one video, without the user clicking each step.

Every step is still an ordinary generation job (credits reserved first, refunded on failure);
this row only remembers which jobs belong to the film and how far it has got."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db
from app.models.base import Timestamps, UUIDPrimaryKey


class FilmStatus(enum.StrEnum):
    PLANNING = "planning"                        # Claude is writing the scene plan
    WAITING_FOR_CREDITS = "waiting_for_credits"  # paused: the balance does not cover the film
    PRODUCING = "producing"                      # images, videos and voices are being made
    ASSEMBLING = "assembling"                    # the clips are being joined into one video
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


ACTIVE_FILM_STATUSES = (FilmStatus.PLANNING, FilmStatus.WAITING_FOR_CREDITS, FilmStatus.PRODUCING,
                        FilmStatus.ASSEMBLING)


class FilmProduction(UUIDPrimaryKey, Timestamps, db.Model):
    __tablename__ = "film_productions"
    __table_args__ = (UniqueConstraint("user_id", "idempotency_key", name="uq_film_productions_user_idempotency"),)

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"),
                                               nullable=False, index=True)
    project_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("projects.id", ondelete="CASCADE"),
                                                  nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[FilmStatus] = mapped_column(
        Enum(FilmStatus, name="film_status", values_callable=lambda e: [m.value for m in e]),
        nullable=False, default=FilmStatus.PLANNING)
    plan_job_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("generation_jobs.id", ondelete="SET NULL"))
    # {"orientation": "landscape" | "portrait"}
    options: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # One entry per scene, in order: {"scene_id", "image_job_id", "video_job_id", "voice_job_id",
    # "skipped": {kind: reason}, "errors": {kind: message}}
    scenes: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    estimated_credits: Mapped[int | None] = mapped_column(Integer)
    film_asset_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("assets.id", ondelete="SET NULL"))
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(String(500))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
