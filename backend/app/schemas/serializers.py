"""Turn models into JSON-safe dicts. Only fields listed here ever leave the API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.models import (
    Asset,
    AuditEvent,
    Character,
    CreditAccount,
    CreditTransaction,
    GenerationJob,
    Project,
    Scene,
    User,
)


def iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def user_out(user: User, *, admin_view: bool = False) -> dict[str, Any]:
    out = {
        "id": str(user.id),
        "email": user.email,
        "display_name": user.profile.display_name if user.profile else "",
        "preferred_language": user.profile.preferred_language if user.profile else None,
        "country": user.profile.country if user.profile else None,
        "role": user.role.value,
        "email_verified": user.email_verified,
        "created_at": iso(user.created_at),
    }
    if admin_view:
        out["is_active"] = user.is_active
        out["last_login_at"] = iso(user.last_login_at)
    return out


def project_out(project: Project, stats: dict[str, int] | None = None) -> dict[str, Any]:
    out = {
        "id": str(project.id),
        "title": project.title,
        "description": project.description,
        "status": project.status.value,
        "brief": project.brief,
        "created_at": iso(project.created_at),
        "updated_at": iso(project.updated_at),
    }
    if stats is not None:
        out.update(stats)
    return out


def character_out(c: Character) -> dict[str, Any]:
    return {
        "id": str(c.id), "project_id": str(c.project_id), "name": c.name,
        "description": c.description, "traits": c.traits,
        "reference_asset_id": str(c.reference_asset_id) if c.reference_asset_id else None,
        "created_at": iso(c.created_at), "updated_at": iso(c.updated_at),
    }


def scene_out(s: Scene) -> dict[str, Any]:
    return {
        "id": str(s.id), "project_id": str(s.project_id), "position": s.position, "title": s.title,
        "description": s.description, "shot_notes": s.shot_notes, "dialogue": s.dialogue,
        "duration_seconds": s.duration_seconds, "ai_prompts": s.ai_prompts or {},
        "character_ids": [str(c.id) for c in s.characters],
        "preview_asset_id": str(s.preview_asset_id) if s.preview_asset_id else None,
        "created_at": iso(s.created_at), "updated_at": iso(s.updated_at),
    }


def asset_out(a: Asset) -> dict[str, Any]:
    return {
        "id": str(a.id), "project_id": str(a.project_id) if a.project_id else None,
        "generation_job_id": str(a.generation_job_id) if a.generation_job_id else None,
        "kind": a.kind.value, "source": a.source.value, "display_name": a.display_name,
        "original_filename": a.original_filename, "mime_type": a.mime_type,
        "size_bytes": a.size_bytes, "width": a.width, "height": a.height,
        "duration_seconds": a.duration_seconds, "provider": a.provider, "model": a.model,
        "created_at": iso(a.created_at),
    }


def job_out(j: GenerationJob, *, admin_view: bool = False) -> dict[str, Any]:
    out = {
        "id": str(j.id), "project_id": str(j.project_id) if j.project_id else None,
        "scene_id": str(j.scene_id) if j.scene_id else None,
        "retry_of_id": str(j.retry_of_id) if j.retry_of_id else None,
        "kind": j.kind.value, "provider": j.provider, "model": j.model, "params": j.input_params,
        "status": j.status.value, "progress": j.progress, "result": j.result,
        "error": {"code": j.error_code, "message": j.error_message} if j.error_code else None,
        "credits_reserved": j.credits_reserved, "credits_charged": j.credits_charged,
        "attempts": j.attempts,
        "created_at": iso(j.created_at), "started_at": iso(j.started_at),
        "completed_at": iso(j.completed_at),
    }
    if admin_view:
        out["user_id"] = str(j.user_id)
        out["usage"] = j.usage
        out["provider_job_id"] = j.provider_job_id
    return out


def credit_account_out(a: CreditAccount) -> dict[str, Any]:
    return {
        "balance": a.balance,
        # Plan credits expire at plan_credits_expire_at and do not roll over; purchased credits
        # (packages, the sign-up grant, admin grants) never expire. Plan credits are spent first.
        "plan_balance": a.plan_balance,
        "plan_credits_expire_at": iso(a.plan_credits_expire_at) if a.plan_balance else None,
        "purchased_balance": a.purchased_balance,
        "updated_at": iso(a.updated_at),
    }


def credit_tx_out(t: CreditTransaction) -> dict[str, Any]:
    return {
        "id": str(t.id), "type": t.tx_type.value, "amount": t.amount, "balance_after": t.balance_after,
        "plan_amount": t.plan_amount, "purchased_amount": t.purchased_amount,
        "generation_job_id": str(t.generation_job_id) if t.generation_job_id else None,
        "reason": t.reason, "created_at": iso(t.created_at),
    }


def audit_out(e: AuditEvent) -> dict[str, Any]:
    return {
        "id": str(e.id), "actor_user_id": str(e.actor_user_id) if e.actor_user_id else None,
        "action": e.action, "target_type": e.target_type, "target_id": e.target_id,
        "ip_address": e.ip_address, "details": e.details, "created_at": iso(e.created_at),
    }


def payment_out(p, *, admin_view: bool = False) -> dict[str, Any]:
    from app.billing.money import format_money, usd_with_reference

    expected = usd_with_reference(p.amount_minor) if p.currency == "USD" else {
        "amount_minor": p.amount_minor, "currency": p.currency,
        "formatted": format_money(p.amount_minor, p.currency)}
    paid = None
    if p.paid_amount_minor is not None and p.paid_currency in ("USD", "KES"):
        paid = {"amount_minor": p.paid_amount_minor, "currency": p.paid_currency,
                "formatted": format_money(p.paid_amount_minor, p.paid_currency)}
    out = {
        "id": str(p.id), "reference": p.reference, "kind": p.kind.value, "item_code": p.item_code,
        "item_name": p.item_name, "status": p.status.value, "price": expected, "amount_paid": paid,
        "credits": p.credits_to_grant, "credits_granted": p.credits_granted_at is not None,
        "channel": p.channel, "failure_reason": p.failure_reason if p.status.value != "succeeded" else None,
        "created_at": iso(p.created_at), "paid_at": iso(p.paid_at),
    }
    if admin_view:
        out["user_id"] = str(p.user_id)
        out["provider_transaction_id"] = p.provider_transaction_id
    return out


def subscription_out(sub) -> dict[str, Any] | None:
    if sub is None:
        return None
    return {
        "plan_code": sub.plan_code, "status": sub.status.value,
        "current_period_end": iso(sub.current_period_end),
        "linked_to_paystack": bool(sub.paystack_subscription_code),
    }
