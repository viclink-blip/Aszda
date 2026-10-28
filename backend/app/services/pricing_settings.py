"""Apply a pricing document (generation credit costs, plan and package credits) to the
admin settings tables, with the same validation as the admin API. Used by
`flask --app wsgi aszda pricing-apply`."""

from __future__ import annotations

import math
import uuid

from sqlalchemy import select

from app.billing.catalog import get_catalog
from app.extensions import db
from app.models import BillingItemSetting, GenerationPrice
from app.providers import registry
from app.services import audit


def _check_rates(where: str, rates, metrics: list[str], require_all: bool) -> dict:
    if not isinstance(rates, dict):
        raise ValueError(f"{where}: must be an object of metric -> number")
    unknown = set(rates) - set(metrics)
    if unknown:
        raise ValueError(f"{where}: unknown metric(s) {sorted(unknown)}; allowed {metrics}")
    if require_all and set(metrics) - set(rates):
        raise ValueError(f"{where}: missing metric(s) {sorted(set(metrics) - set(rates))}")
    for metric, rate in rates.items():
        if isinstance(rate, bool) or not isinstance(rate, (int, float)) or not math.isfinite(rate) or rate < 0:
            raise ValueError(f"{where}.{metric}: must be a non-negative number")
    return rates


def _positive_int(where: str, value, allow_none: bool = True):
    if value is None and allow_none:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{where}: must be a whole number of at least 1")
    return value


def apply_pricing_document(document: dict, *, actor_id: uuid.UUID | None, commit: bool) -> list[str]:
    """Validate everything first, then write. Returns human-readable change lines."""
    changes: list[str] = []
    generation = []
    for i, entry in enumerate(document.get("generation") or []):
        where = f"generation[{i}]"
        adapter = registry.get_adapter(str(entry.get("provider")))
        spec = adapter.get_model(str(entry.get("model"))) if adapter else None
        if spec is None and adapter is not None and entry.get("only_if_offered") is True:
            # For model IDs that depend on the provider account (Google): not an error when this
            # server does not offer the model.
            changes.append(f"{adapter.name}:{entry.get('model')}: skipped (this server does not offer it)")
            continue
        if spec is None:
            raise ValueError(f"{where}: unknown provider/model {entry.get('provider')}:{entry.get('model')}")
        rates = _check_rates(f"{where}.credits_per_1000", entry.get("credits_per_1000"), spec.usage_metrics, True)
        usd = entry.get("provider_usd_per_1000")
        if usd is not None:
            _check_rates(f"{where}.provider_usd_per_1000", usd, spec.usage_metrics, False)
        generation.append((adapter.name, spec.id, rates, _positive_int(f"{where}.minimum_credits",
                           entry.get("minimum_credits", 1), allow_none=False), usd,
                           str(entry.get("provider_price_source") or "")[:255] or None))

    catalog = get_catalog()
    items = []
    for item_type, key in (("plan", "plans"), ("credit_package", "credit_packages")):
        for i, entry in enumerate(document.get(key) or []):
            where = f"{key}[{i}]"
            code = str(entry.get("code"))
            item = catalog.plan(code) if item_type == "plan" else catalog.package(code)
            if item is None:
                raise ValueError(f"{where}: unknown code {code!r}")
            if item_type == "plan" and item.is_free:
                raise ValueError(f"{where}: the Free plan has no paid allowance")
            credits = _positive_int(f"{where}.credits", entry.get("credits"))
            limit = _positive_int(f"{where}.monthly_credit_limit", entry.get("monthly_credit_limit"))
            if item_type == "credit_package" and limit is not None:
                raise ValueError(f"{where}: packages have no monthly limit")
            if credits and limit and limit < credits:
                raise ValueError(f"{where}: monthly_credit_limit must be at least credits")
            items.append((item_type, code, credits, limit, item.name))

    for provider, model, rates, minimum, usd, source in generation:
        row = db.session.scalar(select(GenerationPrice).where(
            GenerationPrice.provider == provider, GenerationPrice.model == model))
        changes.append(f"{provider}:{model}: credits_per_1000={rates}, minimum={minimum}"
                       + ("" if row is None else f" (was {row.credits_per_1000}, minimum={row.minimum_credits})"))
        if commit:
            if row is None:
                row = GenerationPrice(provider=provider, model=model, credits_per_1000={}, minimum_credits=1)
                db.session.add(row)
            row.credits_per_1000, row.minimum_credits = rates, minimum
            row.provider_usd_per_1000, row.provider_price_source, row.enabled = usd, source, True
            row.updated_by_id = actor_id
    for item_type, code, credits, limit, name in items:
        setting = db.session.scalar(select(BillingItemSetting).where(
            BillingItemSetting.item_type == item_type, BillingItemSetting.code == code))
        changes.append(f"{item_type} {name}: credits={credits}" + (f", monthly limit={limit}" if limit else "")
                       + ("" if setting is None else f" (was credits={setting.credits})"))
        if commit:
            if setting is None:
                setting = BillingItemSetting(item_type=item_type, code=code)
                db.session.add(setting)
            setting.credits = credits
            if item_type == "plan":
                setting.monthly_credit_limit = limit
            setting.updated_by_id = actor_id
    if commit:
        audit.record("admin.pricing_document_applied", actor_id=actor_id, target_type="pricing",
                     target_id="document", lines=changes)
        db.session.commit()
    else:
        db.session.rollback()
    return changes
