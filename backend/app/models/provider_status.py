"""The result of the latest admin-run connection test for each AI provider.

Holds no secrets: only whether the test passed, when, and a short error message."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db
from app.models.base import Timestamps, UUIDPrimaryKey


class ProviderStatus(UUIDPrimaryKey, Timestamps, db.Model):
    __tablename__ = "provider_statuses"

    provider: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_test_ok: Mapped[bool | None] = mapped_column(Boolean)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String(500))
    last_error_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_result: Mapped[str | None] = mapped_column(String(500))
    tested_by_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"))
