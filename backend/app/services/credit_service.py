"""Credit balances and the credit ledger.

Rules:
- The backend alone decides balances and costs; the browser only displays them.
- Every balance change writes one CreditTransaction row in the same DB transaction,
  recording how it splits between plan credits and purchased credits.
- Each ledger row has a unique `reference`, so retried code cannot apply it twice.
- Balances are changed under a row lock (SELECT ... FOR UPDATE) so two parallel
  requests cannot both spend the same credits.

Credit policy (docs/CREDITS.md):
- Plan credits (a subscription's monthly allowance) expire at the end of the billing
  period they belong to and never roll over. Purchased credits (packages, the one-time
  sign-up grant, admin grants) never expire.
- Spending uses plan credits first (they expire soonest), then purchased credits.
- A job's actual cost is taken from its reservation in that same order; anything not
  used goes back to the part it came from. Plan credits from a billing period that has
  ended by then are returned and expired again straight away (both rows are recorded),
  so a refund never turns expired plan credits into lasting ones.

Callers own the surrounding transaction (they commit or roll back).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.errors import PaymentRequired
from app.extensions import db
from app.models import CreditAccount, CreditTransaction, CreditTxType


def now() -> datetime:
    return datetime.now(UTC)


def ensure_account(user_id: uuid.UUID) -> None:
    db.session.execute(
        insert(CreditAccount).values(id=uuid.uuid4(), user_id=user_id, balance=0, plan_balance=0,
                                     purchased_balance=0)
        .on_conflict_do_nothing(index_elements=["user_id"])
    )


def get_account(user_id: uuid.UUID) -> CreditAccount:
    """The account, with plan credits whose period has ended already expired."""
    ensure_account(user_id)
    account = db.session.scalar(select(CreditAccount).where(CreditAccount.user_id == user_id))
    if _plan_period_over(account):
        account = _locked_account(user_id)  # expires them under the lock
    return account


def _plan_period_over(account: CreditAccount) -> bool:
    return (account.plan_credits_expire_at is not None and account.plan_credits_expire_at <= now()
            and account.plan_balance > 0)


def _locked_account(user_id: uuid.UUID) -> CreditAccount:
    ensure_account(user_id)
    account = db.session.scalar(
        select(CreditAccount).where(CreditAccount.user_id == user_id).with_for_update()
        .execution_options(populate_existing=True)
    )
    if _plan_period_over(account):
        _expire_plan_credits(account, f"plan-expiry:{account.id}:{account.plan_credits_expire_at.isoformat()}",
                             reason="Plan credits expired at the end of the billing period")
    return account


def _already_applied(reference: str) -> CreditTransaction | None:
    return db.session.scalar(select(CreditTransaction).where(CreditTransaction.reference == reference))


def _write(account: CreditAccount, plan_delta: int, purchased_delta: int, tx_type: CreditTxType,
           reference: str, *, job_id: uuid.UUID | None = None, actor_id: uuid.UUID | None = None,
           reason: str | None = None, details: dict | None = None) -> CreditTransaction:
    """Change a LOCKED account and write the ledger row. The caller checked `reference`."""
    if plan_delta + purchased_delta == 0:
        raise ValueError("Credit amount must not be zero")
    new_plan = account.plan_balance + plan_delta
    new_purchased = account.purchased_balance + purchased_delta
    if new_plan < 0 or new_purchased < 0:
        raise PaymentRequired(
            "You do not have enough credits for this.",
            details={"balance": account.balance, "required": -(plan_delta + purchased_delta)},
        )
    account.plan_balance = new_plan
    account.purchased_balance = new_purchased
    account.balance = new_plan + new_purchased
    tx = CreditTransaction(
        account_id=account.id, tx_type=tx_type, amount=plan_delta + purchased_delta,
        plan_amount=plan_delta, purchased_amount=purchased_delta, balance_after=account.balance,
        reference=reference, generation_job_id=job_id, actor_user_id=actor_id, reason=reason,
        details=details or {},
    )
    db.session.add(tx)
    db.session.flush()
    return tx


def _spend_split(account: CreditAccount, amount: int) -> tuple[int, int]:
    """How much of `amount` comes from plan credits and from purchased credits (plan first)."""
    if amount > account.balance:
        raise PaymentRequired("You do not have enough credits for this.",
                              details={"balance": account.balance, "required": amount})
    from_plan = min(account.plan_balance, amount)
    return from_plan, amount - from_plan


def _apply(user_id: uuid.UUID, amount: int, tx_type: CreditTxType, reference: str, *,
           job_id: uuid.UUID | None = None, actor_id: uuid.UUID | None = None,
           reason: str | None = None, details: dict | None = None) -> CreditTransaction:
    """Add (positive: to purchased credits) or remove (negative: plan credits first) credits."""
    if amount == 0:
        raise ValueError("Credit amount must not be zero")
    account = _locked_account(user_id)
    # Checked after taking the lock, so a concurrent duplicate waits and then sees it.
    existing = _already_applied(reference)
    if existing is not None:
        return existing
    if amount > 0:
        plan_delta, purchased_delta = 0, amount
    else:
        from_plan, from_purchased = _spend_split(account, -amount)
        plan_delta, purchased_delta = -from_plan, -from_purchased
    return _write(account, plan_delta, purchased_delta, tx_type, reference, job_id=job_id,
                  actor_id=actor_id, reason=reason, details=details)


def _expire_plan_credits(account: CreditAccount, reference: str, *, reason: str) -> CreditTransaction | None:
    """Remove all plan credits of a LOCKED account (end of their billing period)."""
    expired_period = account.plan_credits_expire_at
    account.plan_credits_expire_at = None
    if account.plan_balance <= 0 or _already_applied(reference) is not None:
        return None
    return _write(account, -account.plan_balance, 0, CreditTxType.EXPIRE, reference, reason=reason,
                  details={"period_end": expired_period.isoformat() if expired_period else None})


def grant(user_id: uuid.UUID, amount: int, *, reference: str, reason: str,
          actor_id: uuid.UUID | None, details: dict | None = None) -> CreditTransaction:
    """Lasting credits (never expire): admin grants and the sign-up grant."""
    if amount <= 0:
        raise ValueError("Grant amount must be positive")
    return _apply(user_id, amount, CreditTxType.GRANT, reference, actor_id=actor_id, reason=reason,
                  details=details)


def add_purchased(user_id: uuid.UUID, amount: int, *, reference: str, reason: str,
                  details: dict | None = None) -> CreditTransaction:
    """Credits from a paid credit package (never expire)."""
    if amount <= 0:
        raise ValueError("Purchase amount must be positive")
    return _apply(user_id, amount, CreditTxType.PURCHASE, reference, reason=reason, details=details)


def start_plan_period(user_id: uuid.UUID, amount: int, *, expires_at: datetime, reference: str,
                      reason: str, details: dict | None = None) -> CreditTransaction | None:
    """A paid subscription period begins: unused plan credits of the previous period expire
    and this period's allowance is added, valid until `expires_at`. Idempotent on `reference`."""
    account = _locked_account(user_id)
    existing = _already_applied(reference)
    if existing is not None:
        return existing
    _expire_plan_credits(account, f"{reference}:expire-previous",
                         reason="Unused plan credits expired when the next billing period started")
    account.plan_credits_expire_at = expires_at
    if amount <= 0:
        return None
    return _write(account, amount, 0, CreditTxType.PLAN_ALLOWANCE, reference, reason=reason,
                  details={**(details or {}), "expires_at": expires_at.isoformat()})


def set_plan_expiry(user_id: uuid.UUID, expires_at: datetime) -> None:
    """Paystack moved the end of the current billing period (e.g. its next payment date)."""
    account = _locked_account(user_id)
    if account.plan_balance > 0 and account.plan_credits_expire_at is not None:
        account.plan_credits_expire_at = expires_at


def expire_due_plan_credits() -> int:
    """Expire plan credits of every account whose billing period has ended. Run by the
    scheduler; balances are also expired on the next read or spend, so this only keeps
    stored balances tidy. Returns how many accounts were changed."""
    due = db.session.scalars(select(CreditAccount.user_id).where(
        CreditAccount.plan_credits_expire_at <= now(), CreditAccount.plan_balance > 0)).all()
    for user_id in due:
        _locked_account(user_id)
        db.session.commit()
    return len(due)


def adjust(user_id: uuid.UUID, amount: int, *, reference: str, reason: str,
           actor_id: uuid.UUID) -> CreditTransaction:
    return _apply(user_id, amount, CreditTxType.ADJUSTMENT, reference, actor_id=actor_id, reason=reason)


def reserve_for_job(user_id: uuid.UUID, job_id: uuid.UUID, amount: int) -> None:
    if amount <= 0:
        return
    account = _locked_account(user_id)
    reference = f"job:{job_id}:reserve"
    if _already_applied(reference) is not None:
        return
    from_plan, from_purchased = _spend_split(account, amount)
    _write(account, -from_plan, -from_purchased, CreditTxType.RESERVE, reference, job_id=job_id,
           reason="Reserved for generation job",
           details={"plan_period_end": account.plan_credits_expire_at.isoformat()
                    if from_plan and account.plan_credits_expire_at else None})


def settle_job(user_id: uuid.UUID, job_id: uuid.UUID, reserved: int, charged: int, *,
               success: bool) -> None:
    """Return the unused part of a reservation.

    `charged` is what the job really cost (never more than `reserved`). It is taken from
    the reservation plan credits first. The rest goes back to the part it came from:
    a RELEASE on success, a REFUND on failure or cancellation.
    """
    if not 0 <= charged <= reserved:
        raise ValueError("charged must be between 0 and the reserved amount")
    giveback = reserved - charged
    if giveback <= 0:
        return
    tx_type, reference, reason = (
        (CreditTxType.RELEASE, f"job:{job_id}:release", "Unused reservation released") if success else
        (CreditTxType.REFUND, f"job:{job_id}:refund", "Refund for failed or cancelled job"))
    account = _locked_account(user_id)
    if _already_applied(reference) is not None:
        return
    reservation = _already_applied(f"job:{job_id}:reserve")
    reserved_plan = -reservation.plan_amount if reservation else 0
    reserved_purchased = -reservation.purchased_amount if reservation else reserved
    charged_plan = min(charged, reserved_plan)
    back_plan = reserved_plan - charged_plan
    back_purchased = reserved_purchased - (charged - charged_plan)

    period_end = (reservation.details or {}).get("plan_period_end") if reservation else None
    current_end = account.plan_credits_expire_at.isoformat() if account.plan_credits_expire_at else None
    period_over = back_plan > 0 and period_end != current_end
    _write(account, back_plan, back_purchased, tx_type, reference, job_id=job_id, reason=reason,
           details={"plan_period_ended": True} if period_over else None)
    if period_over:
        # These plan credits belong to a billing period that has ended: they stay expired.
        _write(account, -back_plan, 0, CreditTxType.EXPIRE, f"{reference}:expire", job_id=job_id,
               reason="Returned plan credits from a billing period that has ended",
               details={"period_end": period_end})
