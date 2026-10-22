"""Admin-configurable credit settings.

- GenerationPrice: how many credits each AI model costs (per usage metric).
- BillingItemSetting: credits given by each plan (monthly) and credit package, the plan's
  Paystack plan code, and an optional monthly usage limit per plan.

USD prices are NOT stored here: they stay in billing_catalog.json and change only with the
founder's approval. Every change made through the admin API is written to the audit log.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db
from app.models.base import Timestamps, UUIDPrimaryKey


class GenerationPrice(UUIDPrimaryKey, Timestamps, db.Model):
    __tablename__ = "generation_prices"

    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    # ASZDA credits per 1000 units of each usage metric, e.g. {"video_seconds": 32000}.
    credits_per_1000: Mapped[dict] = mapped_column(JSONB, nullable=False)
    minimum_credits: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # What the provider charges ASZDA (USD per 1000 units), for margin reports only.
    provider_usd_per_1000: Mapped[dict | None] = mapped_column(JSONB)
    provider_price_source: Mapped[str | None] = mapped_column(String(255))
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    updated_by_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"))

    __table_args__ = (
        UniqueConstraint("provider", "model", name="uq_generation_prices_provider_model"),
        CheckConstraint("minimum_credits >= 1", name="minimum_credits_positive"),
    )


class BillingItemSetting(UUIDPrimaryKey, Timestamps, db.Model):
    __tablename__ = "billing_item_settings"

    item_type: Mapped[str] = mapped_column(String(20), nullable=False)  # "plan" | "credit_package"
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    credits: Mapped[int | None] = mapped_column(Integer)  # monthly credits (plans) or package credits
    paystack_plan_code: Mapped[str | None] = mapped_column(String(50))
    # Plans only: maximum credits a subscriber can spend on generation per calendar month.
    monthly_credit_limit: Mapped[int | None] = mapped_column(Integer)
    updated_by_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"))

    __table_args__ = (
        UniqueConstraint("item_type", "code", name="uq_billing_item_settings_type_code"),
        CheckConstraint("item_type IN ('plan', 'credit_package')", name="item_type_valid"),
        CheckConstraint("credits IS NULL OR credits > 0", name="credits_positive"),
        CheckConstraint("monthly_credit_limit IS NULL OR monthly_credit_limit > 0", name="limit_positive"),
    )
