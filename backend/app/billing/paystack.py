"""Minimal Paystack client (https://api.paystack.co).

Endpoints and fields were checked against Paystack's official OpenAPI spec
(github.com/PaystackOSS/openapi, dist/paystack.yaml, June 2026) and official docs
code samples (github.com/PaystackOSS/doc-code-snippets); see docs/BILLING.md.

- Amounts are integers in the currency's smallest unit (cents).
- Auth: "Authorization: Bearer <secret key>".
- Webhooks are signed: HMAC-SHA512 of the raw body with the secret key, hex, in the
  "x-paystack-signature" header.
"""

from __future__ import annotations

import hashlib
import hmac
from typing import Any
from urllib.parse import quote

import httpx
from flask import current_app

BASE_URL = "https://api.paystack.co"


class PaystackError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None, retryable: bool = False,
                 code: str | None = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.retryable = retryable
        self.code = code


def secret_key() -> str:
    return current_app.config.get("PAYSTACK_SECRET_KEY", "")


def is_configured() -> bool:
    return bool(secret_key())


def key_mode() -> str | None:
    key = secret_key()
    if key.startswith("sk_live_"):
        return "live"
    if key.startswith("sk_test_"):
        return "test"
    return "unknown" if key else None


def _request(method: str, path: str, body: dict | None = None) -> dict[str, Any]:
    if not is_configured():
        raise PaystackError("Paystack is not configured.", code="paystack_not_configured")
    try:
        response = httpx.request(method, f"{BASE_URL}{path}", json=body,
                                 headers={"Authorization": f"Bearer {secret_key()}"},
                                 timeout=httpx.Timeout(30.0, connect=10.0))
    except httpx.HTTPError as exc:
        raise PaystackError("Paystack could not be reached.", retryable=True) from exc
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    if response.status_code >= 400 or payload.get("status") is not True:
        message = str(payload.get("message") or f"Paystack returned HTTP {response.status_code}")
        raise PaystackError(message, status_code=response.status_code,
                            retryable=response.status_code == 429 or response.status_code >= 500,
                            code=payload.get("code"))
    return payload.get("data") or {}


def initialize_transaction(*, email: str, amount_minor: int, currency: str, reference: str,
                           callback_url: str, metadata: dict, plan: str | None = None) -> dict:
    body: dict[str, Any] = {
        "email": email, "amount": amount_minor, "currency": currency, "reference": reference,
        "callback_url": callback_url, "metadata": metadata,
    }
    if plan:
        # Paystack uses the plan's own amount when a plan is given; we check that the
        # plan's amount and currency match the catalog before checkout and on verification.
        body["plan"] = plan
    return _request("POST", "/transaction/initialize", body)


def verify_transaction(reference: str) -> dict:
    return _request("GET", f"/transaction/verify/{quote(reference, safe='')}")


def fetch_plan(plan_code: str) -> dict:
    return _request("GET", f"/plan/{plan_code}")


def fetch_subscription(subscription_code: str) -> dict:
    return _request("GET", f"/subscription/{subscription_code}")


def disable_subscription(subscription_code: str, email_token: str) -> dict:
    return _request("POST", "/subscription/disable", {"code": subscription_code, "token": email_token})


def signature_is_valid(raw_body: bytes, signature: str | None) -> bool:
    if not signature or not is_configured():
        return False
    expected = hmac.new(secret_key().encode("utf-8"), raw_body, hashlib.sha512).hexdigest()
    return hmac.compare_digest(expected, signature.strip())


def plan_code_of(transaction: dict) -> str | None:
    """`plan` is a string in Paystack's spec but an object in its webhook samples; accept both."""
    plan = transaction.get("plan")
    if isinstance(plan, dict):
        return plan.get("plan_code") or None
    if isinstance(plan, str) and plan:
        return plan
    plan_object = transaction.get("plan_object")
    if isinstance(plan_object, dict):
        return plan_object.get("plan_code") or None
    return None
