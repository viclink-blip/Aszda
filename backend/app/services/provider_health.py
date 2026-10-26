"""Provider readiness for admins: settings present, connection test results, capabilities.

Never returns secret values: only the NAMES of missing environment variables. Connection
tests run only when an admin asks (they call the provider's model/account lookup, never a
generation), and the result is stored in provider_statuses."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import select

from app.errors import APIError, NotFound
from app.extensions import db
from app.models import ProviderStatus
from app.providers import registry
from app.providers.base import ProviderAdapter, ProviderError
from app.services import audit, orchestrator, pricing

log = logging.getLogger(__name__)


def _status_row(name: str) -> ProviderStatus | None:
    return db.session.scalar(select(ProviderStatus).where(ProviderStatus.provider == name))


def describe(adapter: ProviderAdapter) -> dict:
    row = _status_row(adapter.name)
    missing = adapter.missing_settings()
    models = []
    for spec in adapter.model_specs():
        default = adapter.default_model(spec.kind)
        models.append({"id": spec.id, "kind": spec.kind.value,
                       "is_default": default is not None and default.id == spec.id,
                       "priced": pricing.price_for(adapter.name, spec.id) is not None,
                       "deprecated": spec.deprecated,
                       "shutdown_on": spec.shutdown_on.isoformat() if spec.shutdown_on else None,
                       "available": orchestrator.unavailable_reason(adapter, spec) is None,
                       "unavailable_reason": orchestrator.unavailable_reason(adapter, spec)})
    return {
        "name": adapter.name, "label": adapter.label,
        "credentials_configured": not any(m == adapter.credential_env for m in missing),
        "settings_complete": not missing,
        "missing_settings": missing,  # names only, never values
        "enabled": not orchestrator.provider_disabled(adapter.name),
        "capabilities": [k.value for k in orchestrator.kinds_of(adapter)],
        "models": models,
        "connection_test": {
            "available": adapter.connection_test is not None,
            "description": adapter.connection_test,
            "may_charge": adapter.connection_test_may_charge,
        },
        "last_test": None if row is None else {
            "tested_at": row.last_tested_at.isoformat() if row.last_tested_at else None,
            "ok": row.last_test_ok, "result": row.last_result,
            "last_success_at": row.last_success_at.isoformat() if row.last_success_at else None,
            "last_error": row.last_error,
            "last_error_at": row.last_error_at.isoformat() if row.last_error_at else None,
        },
    }


def describe_all() -> list[dict]:
    return [describe(a) for a in registry.all_adapters()]


def note_error(name: str, message: str) -> None:
    """Record a provider problem seen during real generation (e.g. the account ran out of
    credit) so Admin -> Providers shows it. The caller commits."""
    row = _status_row(name) or ProviderStatus(provider=name)
    db.session.add(row)
    row.last_error, row.last_error_at, row.last_test_ok = message[:500], datetime.now(UTC), False


def run_test(name: str, *, actor_id, confirm_charge: bool) -> dict:
    adapter = registry.get_adapter(name)
    if adapter is None:
        raise NotFound("Unknown provider.")
    if adapter.connection_test is None:
        raise APIError("This provider has no connection test.", code="not_supported", status_code=409)
    missing = adapter.missing_settings()
    if missing:
        raise APIError("Set the missing settings first: " + ", ".join(missing), code="provider_not_configured",
                       status_code=409, details={"missing_settings": missing})
    if adapter.connection_test_may_charge and not confirm_charge:
        raise APIError("This test may be charged by the provider. Confirm to run it.",
                       code="charge_confirmation_required", status_code=409)
    now = datetime.now(UTC)
    ok, message = True, ""
    try:
        message = adapter.test_connection()
    except ProviderError as exc:
        ok, message = False, exc.message
    except Exception:  # noqa: BLE001 — never leak raw SDK errors (they can echo request data)
        log.exception("Connection test for %s crashed", name)
        ok, message = False, "The test failed unexpectedly. See the server log."
    row = _status_row(name) or ProviderStatus(provider=name)
    db.session.add(row)
    row.last_tested_at, row.last_test_ok, row.tested_by_id = now, ok, actor_id
    if ok:
        row.last_success_at, row.last_result = now, message[:500]
    else:
        row.last_error, row.last_error_at = message[:500], now
    audit.record("admin.provider_tested", actor_id=actor_id, target_type="provider", target_id=name, ok=ok)
    db.session.commit()
    return describe(adapter)
