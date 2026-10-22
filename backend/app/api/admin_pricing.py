"""Admin: generation credit costs, plan allowances, package credits and a margin analysis.

USD prices are read-only here (they live in billing_catalog.json and change only with the
founder's approval). Every change is audited with its before and after values.
"""

from __future__ import annotations

import math
from decimal import Decimal

from flask import Blueprint, current_app, jsonify
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select

from app.api.common import doc, parse_body
from app.billing.catalog import get_catalog
from app.billing.money import format_money
from app.errors import APIError, NotFound
from app.extensions import db
from app.models import BillingItemSetting, GenerationPrice
from app.providers import registry
from app.security.auth import admin_required, current_user
from app.services import audit, pricing

bp = Blueprint("admin_pricing", __name__, url_prefix="/api/admin/pricing")

# Typical jobs used to explain costs and margins (not limits). Keyed by provider:model,
# falling back to the model's kind.
REFERENCE_JOBS: dict[str, list[tuple[str, dict[str, float]]]] = {
    "text": [("Script draft: 1,500 tokens in, 4,000 out", {"input_tokens": 1500, "output_tokens": 4000}),
             ("Longest allowed answer: 3,000 in, 16,000 out", {"input_tokens": 3000, "output_tokens": 16000})],
    "speech": [("1,000 characters (about 1 minute of speech)", {"characters": 1000}),
               ("4,096 characters (longest allowed)", {"characters": 4096})],
    "runway:gen4.5": [("5-second clip", {"video_seconds": 5}), ("10-second clip (longest)", {"video_seconds": 10})],
    "runway:veo3.1_fast": [("8-second clip, no audio", {"video_seconds": 8}),
                           ("8-second clip with audio", {"video_seconds_with_audio": 8})],
}


class GenerationPriceIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    credits_per_1000: dict[str, float]
    minimum_credits: int = Field(ge=1, le=100_000)
    provider_usd_per_1000: dict[str, float] | None = None
    provider_price_source: str | None = Field(default=None, max_length=255)
    enabled: bool = True

    @field_validator("credits_per_1000", "provider_usd_per_1000")
    @classmethod
    def non_negative(cls, value):
        if value is not None:
            for metric, rate in value.items():
                if not math.isfinite(rate) or rate < 0 or rate > 10_000_000:
                    raise ValueError(f"{metric}: rate must be between 0 and 10,000,000")
        return value


class BillingItemIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    credits: int | None = Field(default=None, ge=1, le=10_000_000)
    paystack_plan_code: str | None = Field(default=None, pattern=r"^PLN_[A-Za-z0-9]+$")
    monthly_credit_limit: int | None = Field(default=None, ge=1, le=10_000_000)


def _fee_rate() -> Decimal:
    return Decimal(str(current_app.config["PAYMENT_FEE_PERCENT"])) / 100


def _reference_jobs(provider: str, spec) -> list[tuple[str, dict]]:
    return REFERENCE_JOBS.get(f"{provider}:{spec.id}") or REFERENCE_JOBS.get(spec.kind.value, [])


def _generation_rows() -> tuple[list[dict], Decimal | None]:
    """All models with their price and reference-job costs. Also returns the highest provider
    cost per credit across priced reference jobs (the worst case for margins)."""
    rows, worst = [], None
    admin_rows = {(r.provider, r.model): r for r in db.session.scalars(select(GenerationPrice))}
    for adapter in registry.all_adapters():
        for spec in adapter.model_specs():
            price = pricing.price_for(adapter.name, spec.id)
            row = admin_rows.get((adapter.name, spec.id))
            jobs = []
            for name, usage in _reference_jobs(adapter.name, spec):
                credits = price.credits_for(usage) if price else None
                usd = price.provider_usd_for(usage) if price else None
                usd_per_credit = Decimal(str(usd)) / credits if credits and usd is not None else None
                if usd_per_credit is not None and (worst is None or usd_per_credit > worst):
                    worst = usd_per_credit
                jobs.append({"name": name, "usage": usage, "credits": credits, "provider_usd": usd})
            rows.append({
                "provider": adapter.name, "provider_label": adapter.label, "configured": adapter.is_configured(),
                "credential_env": adapter.credential_env, "model": spec.id, "label": spec.label,
                "kind": spec.kind.value, "usage_metrics": spec.usage_metrics,
                "source": pricing.price_source(adapter.name, spec.id),
                "price": None if price is None else {
                    "credits_per_1000": price.credits_per_1000, "minimum_credits": price.minimum_credits,
                    "provider_usd_per_1000": price.provider_usd_per_1000 or None,
                    "provider_price_source": row.provider_price_source if row else None,
                },
                "enabled": row.enabled if row else price is not None,
                "reference_jobs": jobs,
            })
    return rows, worst


def _sale_row(item_type: str, code: str, name: str, price_cents: int, credits: int | None,
              worst: Decimal | None, setting: BillingItemSetting | None) -> dict:
    net = Decimal(price_cents) / 100 * (1 - _fee_rate())
    out = {
        "item_type": item_type, "code": code, "name": name,
        "price": {"amount_minor": price_cents, "currency": "USD", "formatted": format_money(price_cents, "USD")},
        "credits": credits,
        "usd_per_credit": float(Decimal(price_cents) / 100 / credits) if credits else None,
        "net_revenue_usd": float(round(net, 4)),
        "max_provider_cost_usd": None, "gross_margin_percent": None,
    }
    if item_type == "plan":
        out["paystack_plan_code"] = setting.paystack_plan_code if setting else None
        out["monthly_credit_limit"] = setting.monthly_credit_limit if setting else None
    if credits and worst is not None and price_cents:
        cost = worst * credits
        out["max_provider_cost_usd"] = float(round(cost, 4))
        out["gross_margin_percent"] = float(round((net - cost) / net * 100, 1))
    return out


@bp.get("")
@doc("Generation costs, plan allowances, package credits and margins", tags=["Admin"], auth="admin")
@admin_required
def overview():
    generation, worst = _generation_rows()
    catalog = get_catalog()
    settings = {(s.item_type, s.code): s for s in db.session.scalars(select(BillingItemSetting))}
    plans = [_sale_row("plan", p.code, p.name, p.price_usd_cents, p.monthly_credits, worst,
                       settings.get(("plan", p.code))) for p in catalog.plans]
    packages = [_sale_row("credit_package", p.code, p.name, p.price_usd_cents, p.credits, worst,
                          settings.get(("credit_package", p.code))) for p in catalog.credit_packages]
    return jsonify({
        "generation": generation, "plans": plans, "credit_packages": packages,
        "assumptions": {
            "payment_fee_percent": str(current_app.config["PAYMENT_FEE_PERCENT"]),
            "worst_case_provider_usd_per_credit": float(worst) if worst is not None else None,
            "explanation": "Maximum provider cost assumes a customer spends every credit on the reference "
                           "job with the highest provider cost per credit. Hosting, storage and support "
                           "costs are not included. Provider prices are what you entered; check them "
                           "against each provider's current price list.",
        },
    })


def _spec_or_404(provider: str, model: str):
    adapter = registry.get_adapter(provider)
    spec = adapter.get_model(model) if adapter else None
    if spec is None:
        raise NotFound("Unknown provider or model.")
    return spec


def _price_snapshot(row: GenerationPrice | None) -> dict | None:
    if row is None:
        return None
    return {"credits_per_1000": row.credits_per_1000, "minimum_credits": row.minimum_credits,
            "provider_usd_per_1000": row.provider_usd_per_1000, "enabled": row.enabled}


@bp.put("/generation/<provider>/<path:model>")
@doc("Set the credit cost of one model", tags=["Admin"], body=GenerationPriceIn, auth="admin")
@admin_required
def set_generation_price(provider: str, model: str):
    spec = _spec_or_404(provider, model)
    data = parse_body(GenerationPriceIn)
    unknown = set(data.credits_per_1000) - set(spec.usage_metrics)
    unknown |= set(data.provider_usd_per_1000 or {}) - set(spec.usage_metrics)
    if unknown:
        raise APIError(f"Unknown usage metric(s) for this model: {', '.join(sorted(unknown))}. "
                       f"Allowed: {', '.join(spec.usage_metrics)}.", code="unknown_metric", status_code=422)
    missing = set(spec.usage_metrics) - set(data.credits_per_1000)
    if missing:
        raise APIError(f"Set a credit rate for every usage metric: missing {', '.join(sorted(missing))}.",
                       code="missing_metric", status_code=422)
    row = db.session.scalar(select(GenerationPrice).where(
        GenerationPrice.provider == provider, GenerationPrice.model == model).with_for_update())
    before = _price_snapshot(row)
    if row is None:
        row = GenerationPrice(provider=provider, model=model, credits_per_1000={}, minimum_credits=1)
        db.session.add(row)
    row.credits_per_1000 = data.credits_per_1000
    row.minimum_credits = data.minimum_credits
    row.provider_usd_per_1000 = data.provider_usd_per_1000
    row.provider_price_source = data.provider_price_source
    row.enabled = data.enabled
    row.updated_by_id = current_user().id
    db.session.flush()
    audit.record("admin.generation_price_set", actor_id=current_user().id, target_type="model",
                 target_id=f"{provider}:{model}"[:64], before=before, after=_price_snapshot(row))
    db.session.commit()
    return overview()


@bp.delete("/generation/<provider>/<path:model>")
@doc("Remove the admin price (falls back to the pricing file, if any)", tags=["Admin"], auth="admin")
@admin_required
def clear_generation_price(provider: str, model: str):
    _spec_or_404(provider, model)
    row = db.session.scalar(select(GenerationPrice).where(
        GenerationPrice.provider == provider, GenerationPrice.model == model))
    if row is not None:
        audit.record("admin.generation_price_cleared", actor_id=current_user().id, target_type="model",
                     target_id=f"{provider}:{model}"[:64], before=_price_snapshot(row))
        db.session.delete(row)
        db.session.commit()
    return overview()


@bp.put("/billing/<item_type>/<code>")
@doc("Set credits (and plan code / monthly limit) for a plan or credit package", tags=["Admin"],
     body=BillingItemIn, auth="admin")
@admin_required
def set_billing_item(item_type: str, code: str):
    catalog = get_catalog()
    if item_type == "plan":
        item = catalog.plan(code)
        if item is not None and item.is_free:
            raise APIError("The Free plan has no paid allowance to configure.", code="free_plan", status_code=422)
    elif item_type == "credit_package":
        item = catalog.package(code)
    else:
        raise NotFound("Unknown item type.")
    if item is None:
        raise NotFound("Unknown plan or package.")
    data = parse_body(BillingItemIn)
    if item_type == "credit_package" and (data.paystack_plan_code or data.monthly_credit_limit):
        raise APIError("Credit packages only have a credit amount.", code="invalid_field", status_code=422)
    if item_type == "plan" and data.credits and data.monthly_credit_limit and data.monthly_credit_limit < data.credits:
        raise APIError("The monthly limit must be at least the plan's monthly credits, or subscribers could "
                       "not use their allowance.", code="limit_below_allowance", status_code=422)
    setting = db.session.scalar(select(BillingItemSetting).where(
        BillingItemSetting.item_type == item_type, BillingItemSetting.code == code).with_for_update())
    before = None if setting is None else {"credits": setting.credits,
                                           "paystack_plan_code": setting.paystack_plan_code,
                                           "monthly_credit_limit": setting.monthly_credit_limit}
    if setting is None:
        setting = BillingItemSetting(item_type=item_type, code=code)
        db.session.add(setting)
    setting.credits = data.credits
    setting.paystack_plan_code = data.paystack_plan_code
    setting.monthly_credit_limit = data.monthly_credit_limit
    setting.updated_by_id = current_user().id
    db.session.flush()
    audit.record("admin.billing_item_set", actor_id=current_user().id, target_type=item_type, target_id=code,
                 before=before, after=data.model_dump())
    db.session.commit()
    return overview()
