"""Plans and credit packages, loaded from billing_catalog.json (the one place prices live)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from flask import current_app

from app.billing.money import usd_with_reference


class CatalogError(ValueError):
    pass


@dataclass(frozen=True)
class Plan:
    code: str
    name: str
    price_usd_cents: int
    interval: str
    monthly_credits: int | None
    paystack_plan_code: str | None
    summary: str

    @property
    def is_free(self) -> bool:
        return self.price_usd_cents == 0

    def unavailable_reason(self) -> str | None:
        if self.is_free:
            return "free_plan"
        if self.monthly_credits is None:
            return "credits_not_configured"
        if not self.paystack_plan_code:
            return "paystack_plan_not_configured"
        return None


@dataclass(frozen=True)
class CreditPackage:
    code: str
    name: str
    price_usd_cents: int
    credits: int | None

    def unavailable_reason(self) -> str | None:
        return "credits_not_configured" if self.credits is None else None


@dataclass(frozen=True)
class Catalog:
    plans: tuple[Plan, ...]
    credit_packages: tuple[CreditPackage, ...]

    def plan(self, code: str) -> Plan | None:
        return next((p for p in self.plans if p.code == code), None)

    def package(self, code: str) -> CreditPackage | None:
        return next((p for p in self.credit_packages if p.code == code), None)

    def plan_by_paystack_code(self, plan_code: str) -> Plan | None:
        return next((p for p in self.plans if p.paystack_plan_code == plan_code), None)


def _positive_int_or_none(value, where: str) -> int | None:
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise CatalogError(f"{where} must be a positive whole number or null")
    return value


def _price(value, where: str) -> int:
    # Integer cents only: 9.99 or "9" would be ambiguous, so they are rejected.
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise CatalogError(f"{where} must be a whole number of US cents (e.g. 900 for $9)")
    return value


def parse_catalog(data: dict) -> Catalog:
    plans, packages, codes = [], [], set()
    for i, raw in enumerate(data.get("plans") or []):
        where = f"plans[{i}]"
        code = str(raw["code"])
        if code in codes:
            raise CatalogError(f"duplicate code {code!r}")
        codes.add(code)
        if raw.get("interval", "month") != "month":
            raise CatalogError(f"{where}.interval: only 'month' is supported")
        plan_code = raw.get("paystack_plan_code")
        if plan_code is not None and not str(plan_code).startswith("PLN_"):
            raise CatalogError(f"{where}.paystack_plan_code must look like PLN_xxxx or be null")
        plans.append(Plan(
            code=code, name=str(raw["name"]),
            price_usd_cents=_price(raw.get("price_usd_cents"), f"{where}.price_usd_cents"),
            interval="month",
            monthly_credits=_positive_int_or_none(raw.get("monthly_credits"), f"{where}.monthly_credits"),
            paystack_plan_code=plan_code, summary=str(raw.get("summary", "")),
        ))
    for i, raw in enumerate(data.get("credit_packages") or []):
        where = f"credit_packages[{i}]"
        code = str(raw["code"])
        if code in codes:
            raise CatalogError(f"duplicate code {code!r}")
        codes.add(code)
        price = _price(raw.get("price_usd_cents"), f"{where}.price_usd_cents")
        if price == 0:
            raise CatalogError(f"{where}: a credit package cannot be free")
        packages.append(CreditPackage(code=code, name=str(raw["name"]), price_usd_cents=price,
                                      credits=_positive_int_or_none(raw.get("credits"), f"{where}.credits")))
    return Catalog(plans=tuple(plans), credit_packages=tuple(packages))


@lru_cache(maxsize=4)
def _load(path: str) -> Catalog:
    return parse_catalog(json.loads(Path(path).read_text(encoding="utf-8")))


_override: Catalog | None = None


def set_override(catalog: Catalog | None) -> None:
    """Tests use this to install a catalog without a file."""
    global _override
    _override = catalog


def get_catalog() -> Catalog:
    if _override is not None:
        return _override
    return _load(current_app.config["BILLING_CATALOG_FILE"])


def plan_out(plan: Plan) -> dict:
    return {
        "code": plan.code, "name": plan.name, "summary": plan.summary, "interval": plan.interval,
        "price": usd_with_reference(plan.price_usd_cents),
        "monthly_credits": plan.monthly_credits,
        "purchasable": plan.unavailable_reason() is None,
        "unavailable_reason": plan.unavailable_reason(),
    }


def package_out(package: CreditPackage) -> dict:
    return {
        "code": package.code, "name": package.name,
        "price": usd_with_reference(package.price_usd_cents),
        "credits": package.credits,
        "purchasable": package.unavailable_reason() is None,
        "unavailable_reason": package.unavailable_reason(),
    }
