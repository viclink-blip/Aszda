"""The AI orchestrator: decides which provider and model handle a request.

Every generation goes through `route()`:
- When the caller names a provider (and optionally a model), exactly that is used. If it
  cannot be used (not configured, switched off, unpriced, retired) the request is refused
  with the reason; there is no silent switch to another provider.
- When the caller names no provider, the provider configured for that kind of work
  (ASZDA_AI_TEXT_PROVIDER, _IMAGE_, _VIDEO_, _VOICE_) is used with its default model. If it
  cannot be used, the providers listed in ASZDA_AI_<KIND>_FALLBACKS are tried in order,
  each with its own default model for the same kind of work. Only providers that really
  offer that kind of work are candidates.

Fallback happens only here, before a job is created and before any credits are reserved.
A job that fails at its provider is never re-sent to another provider automatically, so a
request can never be billed by two providers.
"""

from __future__ import annotations

from dataclasses import dataclass

from flask import current_app

from app.errors import APIError, NotFound, ServiceUnavailable
from app.models import GenerationKind
from app.providers import registry
from app.providers.base import ModelSpec, ProviderAdapter
from app.services import pricing

# Kinds of work the orchestrator routes, with the setting naming the preferred provider.
ROUTED_KINDS: dict[GenerationKind, str] = {
    GenerationKind.TEXT: "AI_TEXT_PROVIDER",
    GenerationKind.IMAGE: "AI_IMAGE_PROVIDER",
    GenerationKind.VIDEO: "AI_VIDEO_PROVIDER",
    GenerationKind.SPEECH: "AI_VOICE_PROVIDER",
}

REASONS = {
    "unknown_provider": "This provider does not exist.",
    "provider_disabled": "This provider is switched off (ASZDA_DISABLED_PROVIDERS).",
    "provider_not_configured": "This provider's API key or required settings are missing.",
    "unsupported_capability": "This provider does not offer this kind of generation.",
    "unsupported_model": "This provider does not offer this model for this kind of generation.",
    "model_retired": "The provider has retired this model.",
    "pricing_not_configured": "No credit price is set for this model (Admin -> Pricing), so it cannot be used.",
}


@dataclass(frozen=True)
class Route:
    adapter: ProviderAdapter
    spec: ModelSpec
    requested_provider: str | None
    requested_model: str | None
    fallback_used: bool
    skipped: tuple[tuple[str, str], ...] = ()  # (provider, reason) tried before this one

    def record(self) -> dict:
        """What is stored on the job so every result can be traced to how it was chosen."""
        return {"provider": self.adapter.name, "model": self.spec.id,
                "requested_provider": self.requested_provider, "requested_model": self.requested_model,
                "fallback_used": self.fallback_used,
                "skipped": [{"provider": p, "reason": r} for p, r in self.skipped]}


def provider_disabled(name: str) -> bool:
    return name in current_app.config.get("DISABLED_PROVIDERS", [])


def unavailable_reason(adapter: ProviderAdapter, spec: ModelSpec | None) -> str | None:
    """Why this provider/model cannot run paid generation right now (None: it can)."""
    if provider_disabled(adapter.name):
        return "provider_disabled"
    if not adapter.is_configured():
        return "provider_not_configured"
    if spec is None:
        return "unsupported_model"
    if spec.is_retired():
        return "model_retired"
    if pricing.price_for(adapter.name, spec.id) is None:
        return "pricing_not_configured"
    return None


def kinds_of(adapter: ProviderAdapter) -> list[GenerationKind]:
    seen: list[GenerationKind] = []
    for spec in adapter.model_specs():
        if spec.kind not in seen:
            seen.append(spec.kind)
    return seen


def default_model(adapter: ProviderAdapter, kind: GenerationKind) -> ModelSpec | None:
    return adapter.default_model(kind)


def preferred_provider(kind: GenerationKind) -> str | None:
    setting = ROUTED_KINDS.get(kind)
    return current_app.config.get(setting) or None if setting else None


def fallback_providers(kind: GenerationKind) -> list[str]:
    setting = ROUTED_KINDS.get(kind)
    return list(current_app.config.get(f"{setting[:-len('_PROVIDER')]}_FALLBACKS", [])) if setting else []


def _explicit(kind: GenerationKind, provider: str, model: str | None) -> Route:
    adapter = registry.get_adapter(provider)
    if adapter is None:
        raise NotFound(f"Unknown provider '{provider}'.", code="unknown_provider")
    if provider_disabled(adapter.name) or not adapter.is_configured():
        # Checked first: an unconfigured provider may not list its models yet.
        reason = "provider_disabled" if provider_disabled(adapter.name) else "provider_not_configured"
        raise ServiceUnavailable(
            f"{adapter.label} is not available: {REASONS[reason]} An administrator needs to set it up.",
            code=reason)
    if kind not in kinds_of(adapter):
        raise APIError(f"{adapter.label} does not offer {kind.value} generation.",
                       code="unsupported_capability", status_code=422)
    spec = adapter.get_model(model) if model else default_model(adapter, kind)
    if spec is None or spec.kind != kind:
        raise APIError(f"{adapter.label} does not offer '{model}' for {kind.value} generation.",
                       code="unsupported_model", status_code=422)
    reason = unavailable_reason(adapter, spec)
    if reason == "model_retired":
        raise APIError(f"{adapter.label} retired '{spec.id}' on {spec.shutdown_on.isoformat()}. "
                       "Choose another model.", code="model_retired", status_code=422)
    if reason == "pricing_not_configured":
        raise APIError(f"Credit pricing for {adapter.label} '{spec.id}' has not been configured yet, so it "
                       "cannot be used. An administrator needs to set it in Admin -> Pricing.",
                       code="pricing_not_configured", status_code=409)
    if reason:
        raise ServiceUnavailable(
            f"{adapter.label} is not available: {REASONS[reason]} An administrator needs to set it up.",
            code=reason)
    return Route(adapter, spec, provider, model, fallback_used=False)


def route(kind: GenerationKind, provider: str | None = None, model: str | None = None) -> Route:
    """Choose the adapter and model for a request (see the module docstring)."""
    if provider:
        return _explicit(kind, provider, model)
    if model:
        raise APIError("Name the provider when choosing a specific model.", code="provider_required",
                       status_code=422)
    if kind not in ROUTED_KINDS:
        raise APIError(f"Choose a provider for {kind.value} generation.", code="provider_required",
                       status_code=422)
    preferred = preferred_provider(kind)
    candidates = [p for p in [preferred, *fallback_providers(kind)] if p]
    skipped: list[tuple[str, str]] = []
    for name in dict.fromkeys(candidates):  # keep order, drop duplicates
        adapter = registry.get_adapter(name)
        if adapter is None:
            skipped.append((name, "unknown_provider"))
            continue
        if provider_disabled(name) or not adapter.is_configured():
            # Checked first: an unconfigured provider may not list its models yet.
            skipped.append((name, "provider_disabled" if provider_disabled(name) else "provider_not_configured"))
            continue
        if kind not in kinds_of(adapter):
            skipped.append((name, "unsupported_capability"))
            continue
        spec = default_model(adapter, kind)
        reason = unavailable_reason(adapter, spec)
        if reason:
            skipped.append((name, reason))
            continue
        return Route(adapter, spec, None, None, fallback_used=name != preferred, skipped=tuple(skipped))
    raise ServiceUnavailable(
        f"No AI provider is ready for {kind.value} generation yet.", code="no_provider_available",
        details={"tried": [{"provider": p, "reason": r, "message": REASONS[r]} for p, r in skipped]})


def capabilities() -> list[dict]:
    """For each kind of work: the configured preference, fallbacks, and what would run now."""
    out = []
    for kind in ROUTED_KINDS:
        try:
            chosen = route(kind)
            ready = {"provider": chosen.adapter.name, "model": chosen.spec.id,
                     "fallback_used": chosen.fallback_used}
            problem = None
        except APIError as exc:
            ready, problem = None, {"code": exc.code, "message": exc.message, "details": exc.details}
        out.append({"kind": kind.value, "preferred_provider": preferred_provider(kind),
                    "fallback_providers": fallback_providers(kind), "ready": ready, "problem": problem})
    return out
