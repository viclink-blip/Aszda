"""Plans, credit packages, checkout (Paystack), payment confirmation, receipts and webhooks."""

from __future__ import annotations

import json
import logging
import uuid

from flask import Blueprint, current_app, jsonify, request
from sqlalchemy import func, select

from app.api.common import doc, page, pagination, parse_body
from app.billing import paystack
from app.billing.catalog import get_catalog, package_out, plan_out
from app.billing.money import reference_rate
from app.errors import NotFound
from app.extensions import db, limiter
from app.models import Payment
from app.schemas.requests import CheckoutIn, PaymentReferenceIn
from app.schemas.serializers import credit_account_out, payment_out, subscription_out
from app.security.auth import current_user, login_required
from app.services import credit_service, payment_service

log = logging.getLogger(__name__)

bp = Blueprint("billing", __name__, url_prefix="/api/billing")


def currency_info() -> dict:
    rate = reference_rate()
    return {
        "display_currency": current_app.config["DISPLAY_CURRENCY"],
        "reference_currency": current_app.config["REFERENCE_CURRENCY"],
        "usd_to_kes_reference_rate": f"{rate.normalize():f}",
        "reference_note": f"KES amounts are for reference only, at a fixed rate of {rate.normalize():f} "
                          "KES per USD set by ASZDA (not a live exchange rate). Prices and charges are in USD.",
    }


@bp.get("/catalog")
@doc("Plans and credit packages with USD prices and KES reference amounts (public)", tags=["Billing"],
     auth="none")
def catalog():
    data = get_catalog()
    status = payment_service.checkout_status()
    return jsonify({
        "currency": currency_info(),
        "plans": [plan_out(p) for p in data.plans],
        "credit_packages": [package_out(p) for p in data.credit_packages],
        "checkout": {"enabled": status["enabled"], "reason": status["reason"], "message": status["message"]},
    })


@bp.get("/overview")
@doc("My plan, credit balance, checkout availability and recent payments", tags=["Billing"])
@login_required
def overview():
    user = current_user()
    account = credit_service.get_account(user.id)
    db.session.commit()
    sub = payment_service.get_subscription(user)
    plan = get_catalog().plan(sub.plan_code) if sub else None
    payments = db.session.scalars(select(Payment).where(Payment.user_id == user.id)
                                  .order_by(Payment.created_at.desc()).limit(10)).all()
    return jsonify({
        "subscription": subscription_out(sub),
        "plan": plan_out(plan) if plan else None,
        "credits": credit_account_out(account),
        "checkout": payment_service.checkout_status(),
        "currency": currency_info(),
        "recent_payments": [payment_out(p) for p in payments],
    })


@bp.post("/checkout")
@doc("Start a Paystack checkout for a plan or credit package (server decides the price)",
     tags=["Billing"], body=CheckoutIn)
@login_required
@limiter.limit("10 per minute")
def checkout():
    data = parse_body(CheckoutIn)
    user = current_user()
    if data.item_type == "credit_package":
        payment, url = payment_service.start_credit_checkout(user, data.item_code)
    else:
        payment, url = payment_service.start_subscription_checkout(user, data.item_code)
    return jsonify({"payment": payment_out(payment), "authorization_url": url}), 201


@bp.post("/confirm")
@doc("Confirm a payment after returning from Paystack (verified with Paystack's API)",
     tags=["Billing"], body=PaymentReferenceIn)
@login_required
@limiter.limit("30 per minute")
def confirm():
    data = parse_body(PaymentReferenceIn)
    payment = payment_service.confirm_payment(data.reference, user=current_user())
    return jsonify({"payment": payment_out(payment)})


@bp.get("/payments")
@doc("My payment history", tags=["Billing"])
@login_required
def list_payments():
    user = current_user()
    limit, offset = pagination()
    query = select(Payment).where(Payment.user_id == user.id)
    total = db.session.scalar(select(func.count()).select_from(query.subquery()))
    items = db.session.scalars(query.order_by(Payment.created_at.desc()).limit(limit).offset(offset)).all()
    return jsonify(page([payment_out(p) for p in items], total, limit, offset))


@bp.get("/payments/<uuid:payment_id>")
@doc("One payment (receipt)", tags=["Billing"])
@login_required
def get_payment(payment_id: uuid.UUID):
    payment = db.session.get(Payment, payment_id)
    if payment is None or payment.user_id != current_user().id:
        raise NotFound("Payment not found.")
    return jsonify({"payment": payment_out(payment), "currency": currency_info(),
                    "seller": {"name": "ASZDA", "product": "ASZDA Studio"}})


@bp.post("/subscription/cancel")
@doc("Cancel my plan at the end of the paid period", tags=["Billing"])
@login_required
def cancel_subscription():
    sub = payment_service.cancel_subscription(current_user())
    return jsonify({"subscription": subscription_out(sub)})


@bp.post("/paystack/webhook")
@doc("Paystack webhook (signed with HMAC-SHA512; configure this URL in the Paystack dashboard)",
     tags=["Billing"], auth="none")
@limiter.exempt
def paystack_webhook():
    raw = request.get_data(cache=False)
    if not paystack.signature_is_valid(raw, request.headers.get("x-paystack-signature")):
        log.warning("Rejected Paystack webhook with an invalid signature from %s", request.remote_addr)
        return jsonify({"error": {"code": "invalid_signature", "message": "Invalid signature."}}), 401
    try:
        event = json.loads(raw)
    except ValueError:
        return jsonify({"error": {"code": "invalid_json", "message": "Invalid JSON."}}), 400
    if not isinstance(event, dict):
        return jsonify({"error": {"code": "invalid_json", "message": "Invalid payload."}}), 400
    outcome = payment_service.handle_webhook(event)
    return jsonify({"received": True, "outcome": outcome})

