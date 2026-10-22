"""Checkout, payment verification, credit fulfilment, webhooks and subscriptions (Paystack).

Rules (docs/BILLING.md):
- The server decides what is sold and for how much, from billing_catalog.json. The browser
  only sends an item code; any amount, currency, rate or credit number it sends is rejected.
- A payment gives value only after Paystack's Verify Transaction API confirms status
  "success" AND the exact expected amount (integer cents) AND the expected currency
  (and, for subscriptions, the expected plan).
- Checkout charges in USD only. If USD checkout is not enabled for the Paystack account,
  checkout is refused; ASZDA never silently charges another currency or amount.
- Fulfilment is idempotent: payment rows are locked while processed and credits use a
  unique ledger reference ("payment:<id>:credits"), so a callback and a webhook arriving
  together (or a webhook retried by Paystack) can never grant credits twice.
"""

from __future__ import annotations

import calendar
import logging
import uuid
from datetime import UTC, datetime, timedelta

from flask import current_app
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.billing import paystack
from app.billing.catalog import get_catalog
from app.errors import APIError, Conflict, NotFound, ServiceUnavailable
from app.extensions import db
from app.models import (
    Payment,
    PaymentEvent,
    PaymentKind,
    PaymentStatus,
    Subscription,
    SubscriptionStatus,
    User,
)
from app.services import audit, credit_service

log = logging.getLogger(__name__)

CHARGE_CURRENCY = "USD"


def now() -> datetime:
    return datetime.now(UTC)


def add_month(moment: datetime) -> datetime:
    month = moment.month % 12 + 1
    year = moment.year + (moment.month == 12)
    day = min(moment.day, calendar.monthrange(year, month)[1])
    return moment.replace(year=year, month=month, day=day)


# ---- Checkout availability ------------------------------------------------------------

def checkout_status() -> dict:
    """Whether checkout can run, and why not. Shown to users and admins."""
    if not paystack.is_configured():
        return {"enabled": False, "reason": "payments_not_configured",
                "message": "Online payments are not switched on yet. Prices are shown for "
                           "information; nothing can be bought right now."}
    if not current_app.config["PAYSTACK_USD_ENABLED"]:
        return {"enabled": False, "reason": "usd_checkout_not_enabled",
                "message": "Checkout in US dollars is not available yet: it is waiting for the "
                           "Paystack account to be confirmed for USD payments. Prices stay in USD; "
                           "ASZDA will not charge you in another currency instead."}
    return {"enabled": True, "reason": None, "message": None, "mode": paystack.key_mode(),
            "currency": CHARGE_CURRENCY}


def _require_checkout() -> None:
    status = checkout_status()
    if not status["enabled"]:
        raise APIError(status["message"], code=status["reason"], status_code=409)


# ---- Starting a checkout ----------------------------------------------------------------

def _new_reference() -> str:
    # Paystack allows letters, digits, "-", "." and "=" in references.
    return f"aszda-{uuid.uuid4().hex}"


def _callback_url() -> str:
    return f"{current_app.config['FRONTEND_URL']}/app/billing/complete"


def _initialize(user: User, payment: Payment, plan_code: str | None = None) -> str:
    """Create the Paystack transaction for a pending payment and return the checkout URL."""
    try:
        data = paystack.initialize_transaction(
            email=user.email, amount_minor=payment.amount_minor, currency=payment.currency,
            reference=payment.reference, callback_url=_callback_url(), plan=plan_code,
            metadata={"payment_id": str(payment.id), "user_id": str(user.id),
                      "kind": payment.kind.value, "item_code": payment.item_code},
        )
    except paystack.PaystackError as exc:
        payment.status = PaymentStatus.FAILED
        payment.failure_reason = f"Checkout could not start: {exc.message}"[:255]
        db.session.commit()
        if "currency" in exc.message.lower():
            raise APIError("Paystack refused to start a USD payment for this account "
                           f"(\"{exc.message}\"). No payment was taken.",
                           code="usd_checkout_rejected", status_code=409) from exc
        raise ServiceUnavailable("The payment page could not be opened. No payment was taken; "
                                 "please try again.", code="checkout_failed") from exc
    url = data.get("authorization_url")
    if not isinstance(url, str) or not url.startswith("https://"):
        payment.status = PaymentStatus.FAILED
        payment.failure_reason = "Paystack returned no checkout link"
        db.session.commit()
        raise ServiceUnavailable("The payment page could not be opened.", code="checkout_failed")
    payment.details = {**payment.details, "access_code": data.get("access_code")}
    db.session.commit()
    return url


def start_credit_checkout(user: User, package_code: str) -> tuple[Payment, str]:
    _require_checkout()
    package = get_catalog().package(package_code)
    if package is None:
        raise NotFound("Unknown credit package.", code="unknown_item")
    if package.credits is None:
        raise APIError(f"The {package.name} package is not on sale yet.", code="credits_not_configured",
                       status_code=409)
    payment = Payment(
        user_id=user.id, kind=PaymentKind.CREDIT_PACKAGE, item_code=package.code, item_name=package.name,
        reference=_new_reference(), currency=CHARGE_CURRENCY, amount_minor=package.price_usd_cents,
        credits_to_grant=package.credits, status=PaymentStatus.PENDING,
    )
    db.session.add(payment)
    db.session.commit()
    return payment, _initialize(user, payment)


def start_subscription_checkout(user: User, plan_code: str) -> tuple[Payment, str]:
    _require_checkout()
    plan = get_catalog().plan(plan_code)
    if plan is None:
        raise NotFound("Unknown plan.", code="unknown_item")
    if plan.is_free:
        raise APIError("The Free plan does not need a payment.", code="free_plan", status_code=409)
    reason = plan.unavailable_reason()
    if reason:
        raise APIError(f"The {plan.name} plan is not on sale yet.", code=reason, status_code=409)
    current = db.session.scalar(select(Subscription).where(Subscription.user_id == user.id))
    if current and current.status in (SubscriptionStatus.ACTIVE, SubscriptionStatus.PAST_DUE):
        raise Conflict("You already have an active plan. Cancel it before choosing another "
                       "(changing plans directly is not supported yet).", code="subscription_exists")

    # Paystack charges the plan's own amount, so make sure the plan set up in the Paystack
    # dashboard matches the catalog exactly before sending anyone to pay.
    try:
        remote = paystack.fetch_plan(plan.paystack_plan_code)
    except paystack.PaystackError as exc:
        raise ServiceUnavailable("This plan's payment set-up could not be checked. No payment was taken.",
                                 code="plan_check_failed") from exc
    if (remote.get("amount") != plan.price_usd_cents
            or str(remote.get("currency", "")).upper() != CHARGE_CURRENCY
            or remote.get("interval") != "monthly"):
        log.error("Paystack plan %s does not match catalog %s: %s", plan.paystack_plan_code, plan.code,
                  {k: remote.get(k) for k in ("amount", "currency", "interval")})
        raise APIError("This plan is temporarily unavailable: its payment set-up does not match the "
                       "published price. No payment was taken.", code="plan_mismatch", status_code=409)

    payment = Payment(
        user_id=user.id, kind=PaymentKind.SUBSCRIPTION, item_code=plan.code, item_name=plan.name,
        reference=_new_reference(), currency=CHARGE_CURRENCY, amount_minor=plan.price_usd_cents,
        credits_to_grant=plan.monthly_credits or 0, status=PaymentStatus.PENDING,
        details={"paystack_plan_code": plan.paystack_plan_code},
    )
    db.session.add(payment)
    db.session.commit()
    return payment, _initialize(user, payment, plan_code=plan.paystack_plan_code)


# ---- Verification and fulfilment ---------------------------------------------------------

def _lock_payment(reference: str) -> Payment | None:
    return db.session.scalar(select(Payment).where(Payment.reference == reference).with_for_update()
                             .execution_options(populate_existing=True))


def _parse_time(value) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _mismatches(payment: Payment, tx: dict) -> list[str]:
    problems = []
    if tx.get("reference") != payment.reference:
        problems.append("reference")
    amount = tx.get("amount")
    if not isinstance(amount, int) or isinstance(amount, bool) or amount != payment.amount_minor:
        problems.append(f"amount (expected {payment.amount_minor}, got {amount!r})")
    if str(tx.get("currency", "")).upper() != payment.currency:
        problems.append(f"currency (expected {payment.currency}, got {tx.get('currency')!r})")
    expected_plan = payment.details.get("paystack_plan_code")
    if expected_plan and paystack.plan_code_of(tx) != expected_plan:
        problems.append("plan")
    return problems


def confirm_payment(reference: str, *, user: User | None = None) -> Payment:
    """Ask Paystack about a payment and give value exactly once if it is correct.

    Safe to call many times, from the browser callback and from webhooks."""
    payment = _lock_payment(reference)
    if payment is None or (user is not None and payment.user_id != user.id):
        db.session.rollback()
        raise NotFound("Payment not found.")
    if payment.status != PaymentStatus.PENDING:
        db.session.rollback()
        return payment  # already final: nothing more to do

    try:
        tx = paystack.verify_transaction(reference)
    except paystack.PaystackError as exc:
        db.session.rollback()
        if exc.status_code == 404:
            return payment  # Paystack has no record yet (checkout not completed)
        raise ServiceUnavailable("We could not confirm the payment with Paystack yet. If you paid, "
                                 "it will be confirmed automatically.", code="verification_unavailable") from exc

    status = tx.get("status")
    payment.details = {**payment.details, "paystack_status": status,
                       "gateway_response": tx.get("gateway_response")}
    if status in ("failed", "abandoned", "reversed"):
        payment.status = PaymentStatus.FAILED
        payment.failure_reason = f"Paystack status: {status}"
        db.session.commit()
        return payment
    if status != "success":
        db.session.commit()
        return payment  # still in progress at Paystack

    payment.paid_amount_minor = tx.get("amount") if isinstance(tx.get("amount"), int) else None
    payment.paid_currency = str(tx.get("currency", ""))[:3].upper() or None
    payment.provider_transaction_id = str(tx.get("id")) if tx.get("id") is not None else None
    payment.channel = str(tx.get("channel"))[:30] if tx.get("channel") else None
    payment.paid_at = _parse_time(tx.get("paid_at")) or now()

    problems = _mismatches(payment, tx)
    if problems:
        # Money arrived but not what we expected: give nothing and flag it for the founder.
        payment.status = PaymentStatus.MISMATCH
        payment.failure_reason = ("Paid amount/currency did not match: " + ", ".join(problems))[:255]
        audit.record("payment.mismatch", actor_id=payment.user_id, target_type="payment",
                     target_id=payment.id, problems=problems)
        db.session.commit()
        log.error("Payment %s mismatch: %s", payment.reference, problems)
        return payment

    payment.status = PaymentStatus.SUCCEEDED
    ledger_details = {"payment_id": str(payment.id), "reference": payment.reference}
    reason = f"{payment.item_name} ({payment.kind.value.replace('_', ' ')})"
    if payment.kind in (PaymentKind.SUBSCRIPTION, PaymentKind.SUBSCRIPTION_RENEWAL):
        sub = _activate_subscription(payment, tx)
        # A new paid period: last period's unused plan credits expire, this period's allowance
        # is valid until the period ends (no rollover).
        credit_service.start_plan_period(payment.user_id, payment.credits_to_grant,
                                         expires_at=sub.current_period_end,
                                         reference=f"payment:{payment.id}:credits", reason=reason,
                                         details=ledger_details)
    elif payment.credits_to_grant > 0:
        credit_service.add_purchased(payment.user_id, payment.credits_to_grant,
                                     reference=f"payment:{payment.id}:credits", reason=reason,
                                     details=ledger_details)
    if payment.credits_to_grant > 0:
        payment.credits_granted_at = now()
    audit.record("payment.succeeded", actor_id=payment.user_id, target_type="payment",
                 target_id=payment.id, amount_minor=payment.amount_minor, currency=payment.currency,
                 item=payment.item_code)
    db.session.commit()
    return payment


def _activate_subscription(payment: Payment, tx: dict) -> Subscription:
    sub = db.session.scalar(select(Subscription).where(Subscription.user_id == payment.user_id)
                            .with_for_update())
    customer_code = (tx.get("customer") or {}).get("customer_code")
    period_end = add_month(payment.paid_at or now())
    if sub is None:
        sub = Subscription(user_id=payment.user_id, plan_code=payment.item_code,
                           status=SubscriptionStatus.ACTIVE)
        db.session.add(sub)
    sub.plan_code = payment.item_code
    sub.status = SubscriptionStatus.ACTIVE
    if not sub.current_period_end or period_end > sub.current_period_end:
        sub.current_period_end = period_end
    if customer_code:
        sub.paystack_customer_code = customer_code
    db.session.flush()
    return sub


# ---- Webhooks ---------------------------------------------------------------------------------

def handle_webhook(event: dict) -> str:
    """Process one verified webhook. Returns a short outcome string.

    Raises on temporary problems so the API answers non-200 and Paystack retries."""
    event_type = str(event.get("event", ""))[:60]
    data = event.get("data") if isinstance(event.get("data"), dict) else {}
    ident = data.get("id") or data.get("reference") or data.get("subscription_code") or data.get("invoice_code")
    event_key = f"{event_type}:{ident}"[:200]
    record = PaymentEvent(event_key=event_key, event_type=event_type, payload=event)
    db.session.add(record)
    try:
        db.session.flush()
    except IntegrityError:
        db.session.rollback()
        return "duplicate"
    db.session.commit()  # remember we received it; processing below is idempotent anyway

    try:
        outcome = _dispatch(event_type, data)
    except Exception:
        # Let Paystack retry: forget the event so the retry is processed.
        db.session.rollback()
        db.session.delete(db.session.get(PaymentEvent, record.id))
        db.session.commit()
        raise
    stored = db.session.get(PaymentEvent, record.id)
    stored.outcome = outcome
    db.session.commit()
    return outcome


def _dispatch(event_type: str, data: dict) -> str:
    if event_type == "charge.success":
        reference = data.get("reference")
        if not isinstance(reference, str) or not reference:
            return "ignored_no_reference"
        if db.session.scalar(select(Payment.id).where(Payment.reference == reference)):
            return f"payment_{confirm_payment(reference).status.value}"
        return _record_renewal(reference, data)
    if event_type == "subscription.create":
        return _sync_subscription(data.get("subscription_code"))
    if event_type in ("subscription.not_renew", "subscription.disable"):
        sub = _subscription_by_code(data.get("subscription_code"))
        if sub is None:
            return "ignored_unknown_subscription"
        sub.status = (SubscriptionStatus.NON_RENEWING if event_type == "subscription.not_renew"
                      else SubscriptionStatus.CANCELLED)
        db.session.commit()
        return f"subscription_{sub.status.value}"
    if event_type == "invoice.payment_failed":
        sub = _subscription_by_code((data.get("subscription") or {}).get("subscription_code"))
        if sub is None:
            return "ignored_unknown_subscription"
        sub.status = SubscriptionStatus.PAST_DUE
        db.session.commit()
        return "subscription_past_due"
    return "ignored_event"


def _subscription_by_code(code) -> Subscription | None:
    if not isinstance(code, str) or not code:
        return None
    return db.session.scalar(select(Subscription).where(Subscription.paystack_subscription_code == code))


def _sync_subscription(code) -> str:
    """Fetch the subscription from Paystack (the webhook body is not trusted for this) and
    link it to the user's local subscription by customer code and plan."""
    if not isinstance(code, str) or not code.startswith("SUB_"):
        return "ignored_no_subscription_code"
    remote = paystack.fetch_subscription(code)
    customer_code = (remote.get("customer") or {}).get("customer_code")
    plan = get_catalog().plan_by_paystack_code(paystack.plan_code_of(remote) or "")
    if not customer_code or plan is None:
        return "ignored_unknown_plan_or_customer"
    sub = db.session.scalar(select(Subscription).where(
        Subscription.paystack_customer_code == customer_code, Subscription.plan_code == plan.code))
    if sub is None:
        return "ignored_unknown_subscription"
    sub.paystack_subscription_code = code
    sub.paystack_email_token = remote.get("email_token") or sub.paystack_email_token
    next_payment = _parse_time(remote.get("next_payment_date"))
    if next_payment:
        sub.current_period_end = next_payment
        # Paystack's next payment date is the real end of the period the plan credits belong to.
        credit_service.set_plan_expiry(sub.user_id, next_payment)
    if remote.get("status") == "active":
        sub.status = SubscriptionStatus.ACTIVE
    db.session.commit()
    return "subscription_linked"


def _record_renewal(reference: str, data: dict) -> str:
    """A charge Paystack made by itself for a subscription renewal (its own reference)."""
    plan = get_catalog().plan_by_paystack_code(paystack.plan_code_of(data) or "")
    customer_code = (data.get("customer") or {}).get("customer_code")
    if plan is None or not customer_code:
        return "ignored_unknown_reference"
    sub = db.session.scalar(select(Subscription).where(
        Subscription.paystack_customer_code == customer_code, Subscription.plan_code == plan.code))
    if sub is None:
        return "ignored_unknown_subscription"
    payment = Payment(
        user_id=sub.user_id, kind=PaymentKind.SUBSCRIPTION_RENEWAL, item_code=plan.code, item_name=plan.name,
        reference=reference[:100], currency=CHARGE_CURRENCY, amount_minor=plan.price_usd_cents,
        credits_to_grant=plan.monthly_credits or 0, status=PaymentStatus.PENDING,
        details={"paystack_plan_code": plan.paystack_plan_code},
    )
    db.session.add(payment)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()  # created by a parallel delivery; confirm below is idempotent
    # Never trust the webhook body for money: confirm with the Verify API.
    return f"renewal_{confirm_payment(reference).status.value}"


# ---- Managing a subscription ---------------------------------------------------------------

def get_subscription(user: User) -> Subscription | None:
    return db.session.scalar(select(Subscription).where(Subscription.user_id == user.id))


def cancel_subscription(user: User) -> Subscription:
    sub = get_subscription(user)
    if sub is None or sub.status not in (SubscriptionStatus.ACTIVE, SubscriptionStatus.PAST_DUE):
        raise Conflict("You do not have an active plan to cancel.", code="no_active_subscription")
    if not (sub.paystack_subscription_code and sub.paystack_email_token):
        raise ServiceUnavailable("Your plan is still being set up with Paystack. Please try again in a "
                                 "few minutes.", code="subscription_not_linked")
    try:
        paystack.disable_subscription(sub.paystack_subscription_code, sub.paystack_email_token)
    except paystack.PaystackError as exc:
        raise ServiceUnavailable("Paystack did not accept the cancellation. Please try again.",
                                 code="cancel_failed") from exc
    sub.status = SubscriptionStatus.NON_RENEWING
    audit.record("subscription.cancelled", actor_id=user.id, target_type="subscription", target_id=sub.id)
    db.session.commit()
    return sub


def expire_overdue_subscriptions() -> int:
    """Non-renewing plans end when their paid period ends (run from the CLI or a scheduler)."""
    count = 0
    for sub in db.session.scalars(select(Subscription).where(
            Subscription.status == SubscriptionStatus.NON_RENEWING,
            Subscription.current_period_end < now() - timedelta(minutes=1))):
        sub.status = SubscriptionStatus.CANCELLED
        count += 1
    db.session.commit()
    # Plan credits of ended billing periods (they are also expired on the next read or spend).
    expired = credit_service.expire_due_plan_credits()
    if expired:
        log.info("Expired plan credits on %s account(s)", expired)
    return count
