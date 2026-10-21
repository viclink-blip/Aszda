"""Real-money payments (Paystack) and subscriptions. Kept separate from internal credits:
a successful payment *grants* credits through a `purchase` ledger entry."""

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
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db
from app.models.base import Timestamps, UUIDPrimaryKey


class PaymentKind(enum.StrEnum):
    CREDIT_PACKAGE = "credit_package"
    SUBSCRIPTION = "subscription"          # first payment of a subscription
    SUBSCRIPTION_RENEWAL = "subscription_renewal"


class PaymentStatus(enum.StrEnum):
    PENDING = "pending"        # checkout started, not paid (yet)
    SUCCEEDED = "succeeded"    # verified with Paystack: right amount and currency
    FAILED = "failed"          # Paystack reports failed/abandoned/reversed
    MISMATCH = "mismatch"      # paid, but amount/currency/plan differ from what we expected: no value given


class Payment(UUIDPrimaryKey, Timestamps, db.Model):
    __tablename__ = "payments"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(20), nullable=False, default="paystack")
    kind: Mapped[PaymentKind] = mapped_column(
        Enum(PaymentKind, name="payment_kind", values_callable=lambda e: [m.value for m in e]), nullable=False
    )
    # The plan or package code from billing_catalog.json, frozen at checkout time.
    item_code: Mapped[str] = mapped_column(String(50), nullable=False)
    item_name: Mapped[str] = mapped_column(String(100), nullable=False)
    # Our transaction reference (Paystack's for renewals it creates itself). Unique: one payment per reference.
    reference: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    # What the server expects to be charged, decided by the server (never the browser).
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    amount_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    credits_to_grant: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus, name="payment_status", values_callable=lambda e: [m.value for m in e]),
        nullable=False, default=PaymentStatus.PENDING,
    )
    # What Paystack reported when we verified (kept for reconciliation and receipts).
    paid_amount_minor: Mapped[int | None] = mapped_column(Integer)
    paid_currency: Mapped[str | None] = mapped_column(String(3))
    provider_transaction_id: Mapped[str | None] = mapped_column(String(50))
    channel: Mapped[str | None] = mapped_column(String(30))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_reason: Mapped[str | None] = mapped_column(String(255))
    credits_granted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    details: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    __table_args__ = (
        Index("ix_payments_user_created", "user_id", "created_at"),
        Index("ix_payments_status", "status"),
        CheckConstraint("amount_minor >= 0", name="amount_non_negative"),
        CheckConstraint("credits_to_grant >= 0", name="credits_non_negative"),
    )


class SubscriptionStatus(enum.StrEnum):
    ACTIVE = "active"
    NON_RENEWING = "non_renewing"   # cancelled; stays usable until current_period_end
    PAST_DUE = "past_due"           # a renewal charge failed
    CANCELLED = "cancelled"


class Subscription(UUIDPrimaryKey, Timestamps, db.Model):
    """The user's paid plan. Users without a row are on the Free plan."""

    __tablename__ = "subscriptions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    plan_code: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[SubscriptionStatus] = mapped_column(
        Enum(SubscriptionStatus, name="subscription_status", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paystack_customer_code: Mapped[str | None] = mapped_column(String(50))
    paystack_subscription_code: Mapped[str | None] = mapped_column(String(50), unique=True)
    # Needed by Paystack to disable the subscription. Treated as a secret: never returned by the API.
    paystack_email_token: Mapped[str | None] = mapped_column(String(100))

    __table_args__ = (Index("ix_subscriptions_customer", "paystack_customer_code"),)


class PaymentEvent(UUIDPrimaryKey, Timestamps, db.Model):
    """Webhooks received. The unique key makes each event processed only once."""

    __tablename__ = "payment_events"

    provider: Mapped[str] = mapped_column(String(20), nullable=False, default="paystack")
    event_key: Mapped[str] = mapped_column(String(200), nullable=False)
    event_type: Mapped[str] = mapped_column(String(60), nullable=False)
    outcome: Mapped[str | None] = mapped_column(String(60))
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    __table_args__ = (UniqueConstraint("provider", "event_key", name="uq_payment_events_provider_key"),)
