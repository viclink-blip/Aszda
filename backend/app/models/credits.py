"""Internal usage credits. Kept separate from real-money payments.

A balance has two parts (docs/CREDITS.md):
- plan credits: the monthly allowance of a subscription. They expire at the end of the
  billing period (plan_credits_expire_at) and never roll over.
- purchased credits: credit packages, the one-time sign-up grant and admin grants.
  They never expire.

Every change to a balance is written to the CreditTransaction ledger in the same
database transaction, with the split between the two parts, so
balance == plan_balance + purchased_balance == sum(ledger amounts) always holds.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Index, Integer, String, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db
from app.models.base import Timestamps, UUIDPrimaryKey


class CreditAccount(UUIDPrimaryKey, Timestamps, db.Model):
    __tablename__ = "credit_accounts"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    # Total spendable credits (plan + purchased), kept for simple reads.
    balance: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    plan_balance: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    purchased_balance: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # When the current plan credits expire (end of the paid billing period). None: no plan credits.
    plan_credits_expire_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("balance >= 0", name="balance_non_negative"),
        CheckConstraint("plan_balance >= 0", name="plan_balance_non_negative"),
        CheckConstraint("purchased_balance >= 0", name="purchased_balance_non_negative"),
        CheckConstraint("balance = plan_balance + purchased_balance", name="balance_is_sum_of_parts"),
    )


class CreditTxType(enum.StrEnum):
    GRANT = "grant"            # admin grant or the one-time sign-up grant (never expires)
    PURCHASE = "purchase"      # credit package bought through a payment (never expires)
    PLAN_ALLOWANCE = "plan_allowance"  # a subscription period's monthly credits
    EXPIRE = "expire"          # unused plan credits removed at the end of their billing period
    RESERVE = "reserve"        # held before a generation job starts
    RELEASE = "release"        # unused part of a reservation returned after success
    REFUND = "refund"          # reservation returned after failure/cancellation
    ADJUSTMENT = "adjustment"  # manual correction by an admin (can be negative)


class CreditTransaction(UUIDPrimaryKey, Timestamps, db.Model):
    __tablename__ = "credit_transactions"

    account_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("credit_accounts.id", ondelete="CASCADE"), nullable=False
    )
    tx_type: Mapped[CreditTxType] = mapped_column(
        Enum(CreditTxType, name="credit_tx_type", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    # Positive adds credits, negative removes them.
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    # How `amount` splits between plan and purchased credits (amount = plan_amount + purchased_amount).
    plan_amount: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    purchased_amount: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    balance_after: Mapped[int] = mapped_column(Integer, nullable=False)
    # A unique reference such as "job:<id>:reserve" makes each ledger entry
    # impossible to apply twice, even if a task is retried.
    reference: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    generation_job_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("generation_jobs.id", ondelete="SET NULL")
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL")
    )
    reason: Mapped[str | None] = mapped_column(String(255))
    details: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    __table_args__ = (
        Index("ix_credit_transactions_account_created", "account_id", "created_at"),
        CheckConstraint("amount <> 0", name="amount_non_zero"),
        CheckConstraint("balance_after >= 0", name="balance_after_non_negative"),
        CheckConstraint("amount = plan_amount + purchased_amount", name="amount_is_sum_of_parts"),
    )


class SignupGrantClaim(UUIDPrimaryKey, Timestamps, db.Model):
    """One row per email address that has received the free sign-up grant.

    Keyed by a hash of the *canonical* address (lower-case, "+tag" removed, dots removed for
    Gmail), and kept when the account is deleted, so deleting and re-creating an account, or
    signing up again with an alias of the same inbox, cannot claim the grant twice."""

    __tablename__ = "signup_grant_claims"

    email_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"))
    credits: Mapped[int] = mapped_column(Integer, nullable=False)
