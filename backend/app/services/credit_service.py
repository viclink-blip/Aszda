"""Credit balances and the credit ledger.

Rules:
- The backend alone decides balances and costs; the browser only displays them.
- Every balance change writes one CreditTransaction row in the same DB transaction.
- Each ledger row has a unique `reference`, so retried code cannot apply it twice.
- Balances are changed under a row lock (SELECT ... FOR UPDATE) so two parallel
  requests cannot both spend the same credits.

Callers own the surrounding transaction (they commit or roll back).
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.errors import PaymentRequired
from app.extensions import db
from app.models import CreditAccount, CreditTransaction, CreditTxType


def ensure_account(user_id: uuid.UUID) -> None:
    db.session.execute(
        insert(CreditAccount).values(id=uuid.uuid4(), user_id=user_id, balance=0)
        .on_conflict_do_nothing(index_elements=["user_id"])
    )


def get_account(user_id: uuid.UUID) -> CreditAccount:
    ensure_account(user_id)
    return db.session.scalar(select(CreditAccount).where(CreditAccount.user_id == user_id))


def _locked_account(user_id: uuid.UUID) -> CreditAccount:
    ensure_account(user_id)
    return db.session.scalar(
        select(CreditAccount).where(CreditAccount.user_id == user_id).with_for_update()
    )


def _already_applied(reference: str) -> CreditTransaction | None:
    return db.session.scalar(select(CreditTransaction).where(CreditTransaction.reference == reference))


def _apply(user_id: uuid.UUID, amount: int, tx_type: CreditTxType, reference: str, *,
           job_id: uuid.UUID | None = None, actor_id: uuid.UUID | None = None,
           reason: str | None = None, details: dict | None = None) -> CreditTransaction:
    if amount == 0:
        raise ValueError("Credit amount must not be zero")
    account = _locked_account(user_id)
    # Checked after taking the lock, so a concurrent duplicate waits and then sees it.
    existing = _already_applied(reference)
    if existing is not None:
        return existing
    new_balance = account.balance + amount
    if new_balance < 0:
        raise PaymentRequired(
            "You do not have enough credits for this.",
            details={"balance": account.balance, "required": -amount},
        )
    account.balance = new_balance
    tx = CreditTransaction(
        account_id=account.id, tx_type=tx_type, amount=amount, balance_after=new_balance,
        reference=reference, generation_job_id=job_id, actor_user_id=actor_id, reason=reason,
        details=details or {},
    )
    db.session.add(tx)
    db.session.flush()
    return tx


def grant(user_id: uuid.UUID, amount: int, *, reference: str, reason: str,
          actor_id: uuid.UUID | None) -> CreditTransaction:
    if amount <= 0:
        raise ValueError("Grant amount must be positive")
    return _apply(user_id, amount, CreditTxType.GRANT, reference, actor_id=actor_id, reason=reason)


def adjust(user_id: uuid.UUID, amount: int, *, reference: str, reason: str,
           actor_id: uuid.UUID) -> CreditTransaction:
    return _apply(user_id, amount, CreditTxType.ADJUSTMENT, reference, actor_id=actor_id, reason=reason)


def reserve_for_job(user_id: uuid.UUID, job_id: uuid.UUID, amount: int) -> None:
    if amount > 0:
        _apply(user_id, -amount, CreditTxType.RESERVE, f"job:{job_id}:reserve", job_id=job_id,
               reason="Reserved for generation job")


def settle_job(user_id: uuid.UUID, job_id: uuid.UUID, reserved: int, charged: int, *,
               success: bool) -> None:
    """Return the unused part of a reservation.

    `charged` is what the job really cost (never more than `reserved`).
    On success the difference is a RELEASE; on failure/cancel it is a REFUND.
    """
    if not 0 <= charged <= reserved:
        raise ValueError("charged must be between 0 and the reserved amount")
    giveback = reserved - charged
    if giveback > 0:
        if success:
            _apply(user_id, giveback, CreditTxType.RELEASE, f"job:{job_id}:release", job_id=job_id,
                   reason="Unused reservation released")
        else:
            _apply(user_id, giveback, CreditTxType.REFUND, f"job:{job_id}:refund", job_id=job_id,
                   reason="Refund for failed or cancelled job")
