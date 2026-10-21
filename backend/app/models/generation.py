"""Generation jobs: one request to an AI provider, tracked from queue to result."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db
from app.models.base import Timestamps, UUIDPrimaryKey


class JobStatus(enum.StrEnum):
    QUEUED = "queued"
    VALIDATING = "validating"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


ACTIVE_STATUSES = (JobStatus.QUEUED, JobStatus.VALIDATING, JobStatus.PROCESSING)
FINAL_STATUSES = (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED)

# Allowed state transitions. Anything else is a programming error.
TRANSITIONS: dict[JobStatus, set[JobStatus]] = {
    JobStatus.QUEUED: {JobStatus.VALIDATING, JobStatus.FAILED, JobStatus.CANCELLED},
    JobStatus.VALIDATING: {JobStatus.PROCESSING, JobStatus.FAILED, JobStatus.CANCELLED},
    # PROCESSING -> QUEUED happens when a temporary provider error schedules a retry
    # before anything was submitted to the provider.
    JobStatus.PROCESSING: {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED, JobStatus.QUEUED},
    JobStatus.COMPLETED: set(),
    JobStatus.FAILED: set(),
    JobStatus.CANCELLED: set(),
}


class GenerationKind(enum.StrEnum):
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    ANIMATION = "animation"
    SPEECH = "speech"


class GenerationJob(UUIDPrimaryKey, Timestamps, db.Model):
    __tablename__ = "generation_jobs"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("projects.id", ondelete="SET NULL")
    )
    scene_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("scenes.id", ondelete="SET NULL")
    )
    # The job this one retries, if any.
    retry_of_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("generation_jobs.id", ondelete="SET NULL")
    )
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)

    kind: Mapped[GenerationKind] = mapped_column(
        Enum(GenerationKind, name="generation_kind", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    # Validated, provider-ready parameters. Reference images are asset IDs, not bytes.
    input_params: Mapped[dict] = mapped_column(JSONB, nullable=False)

    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, name="job_status", values_callable=lambda e: [m.value for m in e]),
        nullable=False, default=JobStatus.QUEUED,
    )
    progress: Mapped[int | None] = mapped_column(Integer)
    provider_job_id: Mapped[str | None] = mapped_column(String(200))
    task_id: Mapped[str | None] = mapped_column(String(200))
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Text outputs (scripts, story concepts) live here; media outputs are Assets.
    result: Mapped[dict | None] = mapped_column(JSONB)
    usage: Mapped[dict | None] = mapped_column(JSONB)
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(Text)

    credits_reserved: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    credits_charged: Mapped[int | None] = mapped_column(Integer)
    credits_settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        # Repeating a request with the same Idempotency-Key returns the same job.
        UniqueConstraint("user_id", "idempotency_key", name="uq_generation_jobs_user_idem"),
        Index("ix_generation_jobs_user_created", "user_id", "created_at"),
        Index("ix_generation_jobs_project_created", "project_id", "created_at"),
        Index("ix_generation_jobs_status", "status"),
        CheckConstraint("credits_reserved >= 0", name="reserved_non_negative"),
        CheckConstraint("credits_charged IS NULL OR credits_charged >= 0", name="charged_non_negative"),
        CheckConstraint("credits_charged IS NULL OR credits_charged <= credits_reserved",
                        name="charged_within_reservation"),
        CheckConstraint("progress IS NULL OR (progress >= 0 AND progress <= 100)", name="progress_range"),
    )

    @property
    def is_active(self) -> bool:
        return self.status in ACTIVE_STATUSES
