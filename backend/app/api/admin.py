"""Administration. Every endpoint requires an admin; every change is audited.

API keys are never returned: providers report only whether a key is configured
and which environment variable holds it.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from flask import Blueprint, jsonify, request
from sqlalchemy import func, or_, select

from app.api.common import doc, page, pagination, parse_body
from app.api.generation import provider_catalog
from app.errors import APIError, NotFound
from app.extensions import db, limiter
from app.models import (
    AuditEvent,
    CreditAccount,
    CreditTransaction,
    CreditTxType,
    GenerationJob,
    JobStatus,
    Project,
    ProviderCost,
    Role,
    User,
)
from app.providers import registry
from app.schemas.requests import AdminCreditIn, AdminUserUpdateIn
from app.schemas.serializers import audit_out, credit_tx_out, job_out, user_out
from app.security.auth import admin_required, current_user
from app.services import audit, auth_service, credit_service, orchestrator, pricing, provider_health

bp = Blueprint("admin", __name__, url_prefix="/api/admin")


@bp.get("/overview")
@doc("Operational numbers for the admin dashboard", tags=["Admin"], auth="admin")
@admin_required
def overview():
    since = datetime.now(UTC) - timedelta(days=30)
    job_counts = dict(db.session.execute(
        select(GenerationJob.status, func.count()).where(GenerationJob.created_at >= since)
        .group_by(GenerationJob.status)).all())
    credits_charged = db.session.scalar(select(func.coalesce(func.sum(GenerationJob.credits_charged), 0))
                                        .where(GenerationJob.created_at >= since))
    return jsonify({
        "period_days": 30,
        "users": {
            "total": db.session.scalar(select(func.count()).select_from(User)),
            "new": db.session.scalar(select(func.count()).select_from(User).where(User.created_at >= since)),
        },
        "projects": db.session.scalar(select(func.count()).select_from(Project)),
        "jobs": {status.value: job_counts.get(status, 0) for status in JobStatus},
        "credits_charged": credits_charged,
        "credits_outstanding": db.session.scalar(select(func.coalesce(func.sum(CreditAccount.balance), 0))),
    })


@bp.get("/users")
@doc("List or search users", tags=["Admin"], auth="admin", query={"q": "email or name"})
@admin_required
def list_users():
    from app.models import UserProfile

    limit, offset = pagination()
    query = select(User).join(UserProfile, UserProfile.user_id == User.id)
    q = (request.args.get("q") or "").strip()[:100]
    if q:
        pattern = f"%{q.replace('%', r'\%').replace('_', r'\_')}%"
        query = query.where(or_(User.email.ilike(pattern, escape="\\"),
                                UserProfile.display_name.ilike(pattern, escape="\\")))
    total = db.session.scalar(select(func.count()).select_from(query.subquery()))
    users = db.session.scalars(query.order_by(User.created_at.desc()).limit(limit).offset(offset)).all()
    balances = dict(db.session.execute(select(CreditAccount.user_id, CreditAccount.balance)
                                       .where(CreditAccount.user_id.in_([u.id for u in users]))).all())
    items = [{**user_out(u, admin_view=True), "credit_balance": balances.get(u.id, 0)} for u in users]
    return jsonify(page(items, total, limit, offset))


@bp.patch("/users/<uuid:user_id>")
@doc("Activate/deactivate a user or change their role", tags=["Admin"], body=AdminUserUpdateIn,
     auth="admin")
@admin_required
def update_user(user_id: uuid.UUID):
    admin = current_user()
    user = db.session.get(User, user_id)
    if user is None:
        raise NotFound("User not found.")
    data = parse_body(AdminUserUpdateIn).model_dump(exclude_unset=True, exclude_none=True)
    if user.id == admin.id and (data.get("is_active") is False or data.get("role") == Role.USER):
        raise APIError("You cannot deactivate or demote your own account.", code="self_modification",
                       status_code=422)
    changes = {}
    if "is_active" in data and data["is_active"] != user.is_active:
        user.is_active = data["is_active"]
        changes["is_active"] = data["is_active"]
        if not user.is_active:
            auth_service.revoke_all_sessions(user.id, "deactivated_by_admin")
    if "role" in data and data["role"] != user.role:
        user.role = data["role"]
        changes["role"] = data["role"].value
        auth_service.revoke_all_sessions(user.id, "role_changed")
    if changes:
        audit.record("admin.user_updated", actor_id=admin.id, target_type="user", target_id=user.id,
                     **changes)
    db.session.commit()
    return jsonify({"user": user_out(user, admin_view=True)})


@bp.post("/users/<uuid:user_id>/credits")
@doc("Grant (positive) or remove (negative) credits, with a reason", tags=["Admin"],
     body=AdminCreditIn, auth="admin")
@admin_required
def adjust_credits(user_id: uuid.UUID):
    admin = current_user()
    if db.session.get(User, user_id) is None:
        raise NotFound("User not found.")
    data = parse_body(AdminCreditIn)
    reference = f"admin:{uuid.uuid4()}"
    if data.amount > 0:
        tx = credit_service.grant(user_id, data.amount, reference=reference, reason=data.reason,
                                  actor_id=admin.id)
    else:
        tx = credit_service.adjust(user_id, data.amount, reference=reference, reason=data.reason,
                                   actor_id=admin.id)
    audit.record("admin.credits_adjusted", actor_id=admin.id, target_type="user", target_id=user_id,
                 amount=data.amount, reason=data.reason, transaction_id=str(tx.id))
    db.session.commit()
    return jsonify({"transaction": credit_tx_out(tx)}), 201


@bp.get("/users/<uuid:user_id>/credits")
@doc("A user's credit ledger", tags=["Admin"], auth="admin")
@admin_required
def user_credits(user_id: uuid.UUID):
    account = credit_service.get_account(user_id)
    db.session.commit()
    limit, offset = pagination()
    query = select(CreditTransaction).where(CreditTransaction.account_id == account.id)
    total = db.session.scalar(select(func.count()).select_from(query.subquery()))
    txs = db.session.scalars(query.order_by(CreditTransaction.created_at.desc()).limit(limit).offset(offset))
    return jsonify({"balance": account.balance,
                    "transactions": page([credit_tx_out(t) for t in txs], total, limit, offset)})


@bp.get("/jobs")
@doc("All generation jobs (filter by status)", tags=["Admin"], auth="admin",
     query={"status": "job status", "provider": "provider name"})
@admin_required
def list_jobs():
    limit, offset = pagination()
    query = select(GenerationJob)
    try:
        if request.args.get("status"):
            query = query.where(GenerationJob.status == JobStatus(request.args["status"]))
    except ValueError as exc:
        raise APIError("Invalid status.", code="invalid_filter") from exc
    if request.args.get("provider"):
        query = query.where(GenerationJob.provider == request.args["provider"][:50])
    total = db.session.scalar(select(func.count()).select_from(query.subquery()))
    jobs = db.session.scalars(query.order_by(GenerationJob.created_at.desc()).limit(limit).offset(offset))
    return jsonify(page([job_out(j, admin_view=True) for j in jobs], total, limit, offset))


@bp.get("/usage")
@doc("Usage and estimated provider cost per provider/model (last N days)", tags=["Admin"],
     auth="admin", query={"days": "1-365, default 30"})
@admin_required
def usage_report():
    try:
        days = max(1, min(int(request.args.get("days", 30)), 365))
    except ValueError as exc:
        raise APIError("days must be a number.", code="invalid_filter") from exc
    since = datetime.now(UTC) - timedelta(days=days)
    jobs = db.session.scalars(select(GenerationJob).where(
        GenerationJob.created_at >= since, GenerationJob.credits_settled_at.is_not(None)))
    rows: dict[tuple[str, str], dict] = {}
    for job in jobs:
        row = rows.setdefault((job.provider, job.model), {
            "provider": job.provider, "model": job.model, "jobs": 0, "completed": 0, "failed": 0,
            "credits_charged": 0, "usage": {}, "estimated_provider_usd": None})
        row["jobs"] += 1
        row["completed"] += job.status == JobStatus.COMPLETED
        row["failed"] += job.status == JobStatus.FAILED
        row["credits_charged"] += job.credits_charged or 0
        for metric, value in ((job.usage or {}).get("actual") or {}).items():
            row["usage"][metric] = row["usage"].get(metric, 0) + value
    for (provider, model), row in rows.items():
        price = pricing.price_for(provider, model)
        if price and price.provider_usd_per_1000:
            row["estimated_provider_usd"] = price.provider_usd_for(row["usage"])
    return jsonify({
        "period_days": days,
        "rows": sorted(rows.values(), key=lambda r: -r["credits_charged"]),
        "note": "estimated_provider_usd is an estimate from the configured provider prices, "
                "not an invoice. It is null when no provider price is configured.",
    })


@bp.get("/providers")
@doc("Provider availability (never shows API keys)", tags=["Admin"], auth="admin")
@admin_required
def providers():
    catalog = provider_catalog()
    for entry in catalog:
        adapter = registry.get_adapter(entry["name"])
        entry["credential_env"] = adapter.credential_env
    return jsonify({"providers": catalog})


@bp.get("/providers/health")
@doc("Provider readiness: missing settings (names only), capabilities, models, last connection test, "
     "and what each kind of work would use", tags=["Admin"], auth="admin")
@admin_required
def providers_health():
    data = provider_health.describe_all()
    db.session.commit()
    return jsonify({"providers": data, "routing": orchestrator.capabilities()})


@bp.post("/providers/<name>/test")
@doc("Run a provider's connection test (no generation). Body: {\"confirm_charge\": true} when the "
     "test may be charged", tags=["Admin"], auth="admin")
@admin_required
@limiter.limit("6 per minute")
def provider_test(name: str):
    body = request.get_json(silent=True) or {}
    result = provider_health.run_test(name, actor_id=current_user().id,
                                      confirm_charge=body.get("confirm_charge") is True)
    return jsonify({"provider": result})


@bp.get("/provider-costs")
@doc("What ASZDA paid providers (estimated from entered provider prices) vs credits charged, by "
     "provider, model and outcome", tags=["Admin"], auth="admin", query={"days": "1-365, default 30"})
@admin_required
def provider_costs():
    try:
        days = min(365, max(1, int(request.args.get("days", 30))))
    except ValueError as exc:
        raise APIError("days must be a number.", code="invalid_filter") from exc
    since = datetime.now(UTC) - timedelta(days=days)
    rows = db.session.execute(
        select(ProviderCost.provider, ProviderCost.model, ProviderCost.outcome, ProviderCost.absorbed_by_aszda,
               func.count(), func.sum(ProviderCost.estimated_usd), func.count(ProviderCost.estimated_usd),
               func.sum(ProviderCost.credits_charged_to_customer))
        .where(ProviderCost.created_at >= since)
        .group_by(ProviderCost.provider, ProviderCost.model, ProviderCost.outcome, ProviderCost.absorbed_by_aszda)
    ).all()
    return jsonify({
        "period_days": days,
        "rows": [{"provider": p, "model": m, "outcome": o, "absorbed_by_aszda": a, "jobs": n,
                  "estimated_usd": str(usd) if usd is not None else None, "jobs_with_estimate": n_est,
                  "credits_charged": credits or 0} for p, m, o, a, n, usd, n_est, credits in rows],
        "note": "estimated_usd uses the provider prices entered in Admin -> Pricing; it is not an invoice. "
                "Jobs without an entered provider price have no estimate. Provider-reported figures are "
                "kept on each record (provider_reported).",
    })


@bp.get("/audit-events")
@doc("Security and admin audit log", tags=["Admin"], auth="admin", query={"action": "filter by action"})
@admin_required
def audit_events():
    limit, offset = pagination(default_limit=50)
    query = select(AuditEvent)
    if request.args.get("action"):
        query = query.where(AuditEvent.action == request.args["action"][:80])
    total = db.session.scalar(select(func.count()).select_from(query.subquery()))
    events = db.session.scalars(query.order_by(AuditEvent.created_at.desc()).limit(limit).offset(offset))
    return jsonify(page([audit_out(e) for e in events], total, limit, offset))


@bp.get("/credit-transactions")
@doc("Recent credit transactions across all users", tags=["Admin"], auth="admin",
     query={"type": "grant|purchase|reserve|release|refund|adjustment"})
@admin_required
def credit_transactions():
    limit, offset = pagination(default_limit=50)
    query = select(CreditTransaction)
    if request.args.get("type"):
        try:
            query = query.where(CreditTransaction.tx_type == CreditTxType(request.args["type"]))
        except ValueError as exc:
            raise APIError("Invalid type.", code="invalid_filter") from exc
    total = db.session.scalar(select(func.count()).select_from(query.subquery()))
    txs = db.session.scalars(query.order_by(CreditTransaction.created_at.desc()).limit(limit).offset(offset))
    return jsonify(page([credit_tx_out(t) for t in txs], total, limit, offset))


@bp.get("/payments")
@doc("All payments (filter by status); amounts are what Paystack confirmed", tags=["Admin"], auth="admin",
     query={"status": "pending|succeeded|failed|mismatch"})
@admin_required
def list_payments():
    from app.models import Payment, PaymentStatus
    from app.schemas.serializers import payment_out
    from app.services import payment_service

    limit, offset = pagination()
    query = select(Payment)
    if request.args.get("status"):
        try:
            query = query.where(Payment.status == PaymentStatus(request.args["status"]))
        except ValueError as exc:
            raise APIError("Invalid status.", code="invalid_filter") from exc
    total = db.session.scalar(select(func.count()).select_from(query.subquery()))
    items = db.session.scalars(query.order_by(Payment.created_at.desc()).limit(limit).offset(offset))
    return jsonify({**page([payment_out(p, admin_view=True) for p in items], total, limit, offset),
                    "checkout": payment_service.checkout_status()})
