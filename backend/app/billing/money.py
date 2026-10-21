"""Money helpers.

Rules:
- Money is stored and compared as INTEGER minor units (USD cents, KES cents).
- Conversions use Decimal, never float, and round half-up to a whole minor unit.
- The KES amount is a *reference* calculated with the founder's fixed rate. It is
  shown next to the USD price, clearly labelled, and is never what we charge.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from flask import current_app

# ISO 4217 code -> (symbol shown before the amount, number of minor-unit digits)
CURRENCIES: dict[str, tuple[str, int]] = {
    "USD": ("$", 2),
    "KES": ("KSh ", 2),
}


class MoneyError(ValueError):
    pass


@dataclass(frozen=True)
class Money:
    amount_minor: int
    currency: str

    def __post_init__(self):
        if not isinstance(self.amount_minor, int) or isinstance(self.amount_minor, bool):
            raise MoneyError("amount_minor must be an integer")
        if self.currency not in CURRENCIES:
            raise MoneyError(f"Unsupported currency {self.currency!r}")

    def formatted(self) -> str:
        return format_money(self.amount_minor, self.currency)

    def as_dict(self) -> dict:
        return {"amount_minor": self.amount_minor, "currency": self.currency, "formatted": self.formatted()}


def format_money(amount_minor: int, currency: str) -> str:
    """$9, $9.50, KSh 1,197, KSh 1,197.50 — whole amounts are shown without decimals."""
    symbol, digits = CURRENCIES[currency]
    sign = "-" if amount_minor < 0 else ""
    major, minor = divmod(abs(amount_minor), 10**digits)
    text = f"{major:,}"
    if minor:
        text += f".{minor:0{digits}d}"
    return f"{sign}{symbol}{text}"


def reference_rate() -> Decimal:
    """The configured USD -> KES reference rate (e.g. 133). Validated as a positive decimal."""
    raw = str(current_app.config["USD_TO_KES_REFERENCE_RATE"]).strip()
    try:
        rate = Decimal(raw)
    except InvalidOperation as exc:
        raise MoneyError(f"ASZDA_USD_TO_KES_REFERENCE_RATE is not a number: {raw!r}") from exc
    if not rate.is_finite() or rate <= 0:
        raise MoneyError("ASZDA_USD_TO_KES_REFERENCE_RATE must be a positive number")
    return rate


def convert_minor(amount_minor: int, rate: Decimal) -> int:
    """Convert minor units with a Decimal rate, rounding half-up to a whole minor unit.
    Works because USD and KES both have two minor-unit digits."""
    return int((Decimal(amount_minor) * rate).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def usd_with_reference(amount_usd_cents: int) -> dict:
    """The USD price plus its clearly labelled KES reference amount."""
    rate = reference_rate()
    usd = Money(amount_usd_cents, "USD")
    kes = Money(convert_minor(amount_usd_cents, rate), current_app.config["REFERENCE_CURRENCY"])
    return {
        **usd.as_dict(),
        "reference": {
            **kes.as_dict(),
            "rate": f"{rate.normalize():f}",
            "label": f"Reference only, at a fixed rate of {rate.normalize():f} KES per USD. "
                     "You are charged in USD.",
        },
    }
