"""Credit pricing for provider models.

ASZDA's credit prices are a business decision for the founder, so nothing is
priced by default. A model without a price cannot be used for generation.

Prices live in a JSON file pointed to by ASZDA_PRICING_FILE. Format:

{
  "models": {
    "anthropic:claude-opus-5-5": {
      "credits_per_1000": {"input_tokens": 1, "output_tokens": 5},
      "minimum_credits": 1,
      "provider_usd_per_1000": {"input_tokens": 0.004, "output_tokens": 0.02}
    }
  }
}

- credits_per_1000: ASZDA credits charged per 1000 units of each usage metric.
  The metric names come from each provider adapter (see estimate_usage()).
- minimum_credits: the smallest charge for one job.
- provider_usd_per_1000 (optional): what the provider charges us, used only for
  admin cost reports. Leave it out when you do not have verified provider pricing.
"""

from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from flask import current_app


@dataclass(frozen=True)
class ModelPrice:
    credits_per_1000: dict[str, float]
    minimum_credits: int = 1
    provider_usd_per_1000: dict[str, float] = field(default_factory=dict)

    def credits_for(self, usage: dict[str, float]) -> int:
        total = sum(usage.get(metric, 0) * rate / 1000 for metric, rate in self.credits_per_1000.items())
        return max(self.minimum_credits, math.ceil(total))

    def provider_usd_for(self, usage: dict[str, float]) -> float | None:
        if not self.provider_usd_per_1000:
            return None
        return round(sum(usage.get(m, 0) * r / 1000 for m, r in self.provider_usd_per_1000.items()), 6)


class PricingError(ValueError):
    pass


log = logging.getLogger(__name__)


def _file_prices() -> dict[str, ModelPrice]:
    """Prices from ASZDA_PRICING_FILE. A missing or broken file is logged and treated as empty
    (admin prices still apply) instead of breaking every page that lists models."""
    path = current_app.config.get("PRICING_FILE", "")
    try:
        return _load(path)
    except (OSError, ValueError) as exc:
        log.error("Pricing file %r could not be read (%s); only admin prices are used.", path, exc)
        return {}


@lru_cache(maxsize=8)
def _load(path: str) -> dict[str, ModelPrice]:
    if not path:
        return {}
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    prices: dict[str, ModelPrice] = {}
    for key, entry in (data.get("models") or {}).items():
        rates = entry.get("credits_per_1000")
        if not isinstance(rates, dict) or not rates:
            raise PricingError(f"{key}: credits_per_1000 must be a non-empty object")
        if any((not isinstance(v, (int, float))) or v < 0 for v in rates.values()):
            raise PricingError(f"{key}: rates must be non-negative numbers")
        minimum = int(entry.get("minimum_credits", 1))
        if minimum < 1:
            raise PricingError(f"{key}: minimum_credits must be at least 1")
        prices[key] = ModelPrice(credits_per_1000=rates, minimum_credits=minimum,
                                 provider_usd_per_1000=entry.get("provider_usd_per_1000") or {})
    return prices


_overrides: dict[str, ModelPrice] | None = None


def set_override(prices: dict[str, ModelPrice] | None) -> None:
    """Tests use this to install prices without a file."""
    global _overrides
    _overrides = prices


def price_from_row(row) -> ModelPrice:
    return ModelPrice(credits_per_1000=dict(row.credits_per_1000), minimum_credits=row.minimum_credits,
                      provider_usd_per_1000=dict(row.provider_usd_per_1000 or {}))


def price_source(provider: str, model: str) -> str | None:
    """Where a model's price comes from: "admin", "file" or None (not priced)."""
    if _overrides is not None:
        return "override" if f"{provider}:{model}" in _overrides else None
    row = _admin_row(provider, model)
    if row is not None:
        return "admin" if row.enabled else None
    return "file" if f"{provider}:{model}" in _file_prices() else None


def _admin_row(provider: str, model: str):
    from sqlalchemy import select

    from app.extensions import db
    from app.models import GenerationPrice

    return db.session.scalar(select(GenerationPrice).where(
        GenerationPrice.provider == provider, GenerationPrice.model == model))


def price_for(provider: str, model: str) -> ModelPrice | None:
    """Admin settings (database) win; the pricing file is the fallback. A disabled admin row
    means "not for sale" even if the file prices it."""
    if _overrides is not None:
        return _overrides.get(f"{provider}:{model}")
    row = _admin_row(provider, model)
    if row is not None:
        return price_from_row(row) if row.enabled else None
    return _file_prices().get(f"{provider}:{model}")
