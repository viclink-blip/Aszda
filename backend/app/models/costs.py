"""What ASZDA pays AI providers, recorded per generation job for reconciliation.

This is ASZDA's business cost, separate from the customer's credits: for example a video
that Runway's safety system blocks is refunded to the customer in full, while the amount
Runway billed for it is recorded here as a cost ASZDA absorbs.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Index, Numeric, String, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db
from app.models.base import Timestamps, UUIDPrimaryKey


class ProviderCost(UUIDPrimaryKey, Timestamps, db.Model):
    __tablename__ = "provider_costs"

    # Unique per job and kind ("job:<id>:provider_cost"), so a repeated poll or task
    # cannot record the same cost twice.
    reference: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    generation_job_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("generation_jobs.id", ondelete="SET NULL"))
    user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"))
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    # completed | safety_blocked | failed_billed
    outcome: Mapped[str] = mapped_column(String(30), nullable=False)
    usage: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # Estimated from the provider prices entered in Admin -> Pricing (None when none are entered).
    estimated_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    # What the provider itself reported, when its API returns a cost (e.g. Runway API credits).
    provider_reported: Mapped[dict | None] = mapped_column(JSONB)
    credits_charged_to_customer: Mapped[int] = mapped_column(nullable=False, default=0)
    # True when ASZDA pays the provider but the customer was refunded (e.g. safety blocks).
    absorbed_by_aszda: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (Index("ix_provider_costs_created", "created_at"),)
