"""Internal usage credits. Kept separate from real-money payments.

Every change to a balance is written to the CreditTransaction ledger in the same
database transaction, so balance == sum(ledger amounts) always holds.
"""

from __future__ import annotations

import enum
import uuid

from sqlalchemy import CheckConstraint, Enum, ForeignKey, Index, Integer, String, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db
from app.models.base import Timestamps, UUIDPrimaryKey


class CreditAccount(UUIDPrimaryKey, Timestamps, db.Model):
    __tablename__ = "credit_accounts"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    balance: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (CheckConstraint("balance >= 0", name="balance_non_negative"),)


class CreditTxType(enum.StrEnum):
    GRANT = "grant"            # admin or promotional grant
    PURCHASE = "purchase"      # future: credits bought through a payment
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
    )
