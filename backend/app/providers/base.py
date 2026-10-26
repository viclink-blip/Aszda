"""The contract every AI provider adapter implements.

Business logic (jobs, credits, assets) only talks to this interface, never to a
vendor's API directly, so providers can be added, swapped or replaced by ASZDA's
own models later without touching the rest of the application.

Lifecycle of one generation:
    validate()        -> clean, provider-ready parameters (or a ValidationError)
    estimate_usage()  -> an upper bound of usage, priced into a credit reservation
    submit()          -> either the finished result (synchronous providers) or a
                         provider job ID to poll (asynchronous providers)
    poll()            -> for asynchronous providers, until finished
    cancel()          -> best-effort cancellation, when the provider supports it
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any, Literal

from flask import current_app
from pydantic import BaseModel

from app.models import AssetKind, GenerationKind


@dataclass(frozen=True)
class SettingField:
    """Describes one setting so the web app can render only supported controls."""

    name: str
    label: str
    type: Literal["text", "textarea", "select", "integer", "number", "boolean", "asset"]
    required: bool = False
    help: str | None = None
    options: list[dict[str, str]] | None = None  # for "select": [{"value", "label"}]
    minimum: float | None = None
    maximum: float | None = None
    max_length: int | None = None
    default: Any = None
    asset_kind: str | None = None  # for "asset": which asset kind is accepted
    show_when: dict[str, list[str]] | None = None  # e.g. {"mode": ["image_to_video"]}


@dataclass(frozen=True)
class ModelSpec:
    id: str
    label: str
    kind: GenerationKind
    description: str
    params_model: type[BaseModel]
    fields: list[SettingField]
    usage_metrics: list[str]
    # Provider-announced retirement: shown to users, and the model is refused from this date.
    deprecated: str | None = None      # a short note, e.g. "Deprecated by OpenAI"
    shutdown_on: date | None = None

    def is_retired(self, today: date | None = None) -> bool:
        return self.shutdown_on is not None and (today or datetime.now(UTC).date()) >= self.shutdown_on


@dataclass
class ProviderOutput:
    kind: AssetKind
    mime_type: str
    display_name: str
    data: bytes | None = None
    # For large media, a callable that streams the bytes (avoids holding a video in memory).
    open_stream: Callable[[], Any] | None = None
    duration_seconds: float | None = None
    width: int | None = None
    height: int | None = None


@dataclass
class ProviderOutcome:
    status: Literal["completed", "pending"]
    provider_job_id: str | None = None
    progress: int | None = None
    outputs: list[ProviderOutput] = field(default_factory=list)
    result: dict[str, Any] | None = None
    usage: dict[str, float] = field(default_factory=dict)


class ProviderError(Exception):
    """A provider call failed.

    retryable: the same request may succeed later (rate limit, outage, timeout).
    usage:     anything the provider says it billed despite the failure that the
               user is charged for (for example a refused text request).
    absorbed_usage: usage the provider bills ASZDA for but the user is NOT charged
               (for example a video blocked by the provider's safety system). It is
               recorded as ASZDA's business cost; the user gets a full refund.
    provider_reported: any cost figure the provider returned, kept for reconciliation.
    """

    def __init__(self, message: str, *, code: str = "provider_error", retryable: bool = False,
                 usage: dict[str, float] | None = None, absorbed_usage: dict[str, float] | None = None,
                 provider_reported: dict[str, Any] | None = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.retryable = retryable
        self.usage = usage or {}
        self.absorbed_usage = absorbed_usage or {}
        self.provider_reported = provider_reported


@dataclass
class JobContext:
    job_id: uuid.UUID
    model: str
    params: dict[str, Any]
    provider_job_id: str | None
    # Loads an owned asset's bytes and MIME type; used for reference images.
    load_asset: Callable[[uuid.UUID], tuple[bytes, str]]


class ProviderAdapter(ABC):
    name: str
    label: str
    supports_cancel: bool = False
    #: Name of the environment variable holding the credential (shown to admins, never the value).
    credential_env: str

    #: What the connection test does, shown to admins before they run it. None: no test.
    connection_test: str | None = None
    #: True when the connection test may be billed by the provider.
    connection_test_may_charge: bool = False

    @abstractmethod
    def is_configured(self) -> bool: ...

    def missing_settings(self) -> list[str]:
        """Names of required environment variables that are not set (never their values)."""
        return [] if self.is_configured() else [self.credential_env]

    def params_for_brief(self, model: ModelSpec, brief: dict[str, Any]) -> dict[str, Any]:
        """Turn a provider-neutral request from the AI Film Director into this model's params.

        brief keys: prompt, text, duration_seconds, orientation ("landscape"|"portrait"),
        reference_asset_id (optional image), style (optional)."""
        raise ProviderError(f"{self.label} cannot be used by the AI Film Director for {model.kind.value}.",
                            code="unsupported_capability")

    def test_connection(self) -> str:
        """Check the credential with a request that does not generate anything. Returns a short
        human-readable result; raises ProviderError on failure."""
        raise ProviderError("This provider has no connection test.", code="not_supported")

    @abstractmethod
    def model_specs(self) -> list[ModelSpec]: ...

    def get_model(self, model_id: str) -> ModelSpec | None:
        return next((m for m in self.model_specs() if m.id == model_id), None)

    #: Config keys naming this provider's default model per kind of work (first match wins).
    default_model_settings: dict[GenerationKind, str] = {}

    def default_model(self, kind: GenerationKind) -> ModelSpec | None:
        """The model used when a request names this provider but no model: the one set in the
        configuration for this kind of work, else the first model of that kind."""
        specs = [m for m in self.model_specs() if m.kind == kind]
        setting = self.default_model_settings.get(kind)
        wanted = current_app.config.get(setting) if setting else None
        if wanted:
            return next((m for m in specs if m.id == wanted), None)
        return specs[0] if specs else None

    def validate(self, model: ModelSpec, raw: dict[str, Any]) -> dict[str, Any]:
        """Validate with the model's pydantic schema. Raises pydantic.ValidationError."""
        return model.params_model.model_validate(raw).model_dump(mode="json", exclude_none=True)

    @abstractmethod
    def estimate_usage(self, model: ModelSpec, params: dict[str, Any]) -> dict[str, float]:
        """An upper bound of usage; the credit reservation is based on it."""

    @abstractmethod
    def submit(self, ctx: JobContext) -> ProviderOutcome: ...

    def poll(self, ctx: JobContext) -> ProviderOutcome:
        raise NotImplementedError(f"{self.name} does not use polling")

    def cancel(self, ctx: JobContext) -> bool:
        return False


def out_of_credit(provider_label: str) -> ProviderError:
    """The provider account itself has no credit or quota left (not a temporary rate limit).
    Not retried: retrying cannot succeed until an administrator tops the account up."""
    return ProviderError(
        f"ASZDA's {provider_label} account has run out of credit, so this could not be made. "
        "Your credits were returned. An administrator needs to top up the provider account.",
        code="provider_out_of_credit")


def provider_error_text(response) -> str:
    """The provider's own short error message from a JSON error body, if any (for logs and
    error messages; never contains our credentials)."""
    try:
        body = response.json()
    except ValueError:
        return ""
    error = body.get("error") if isinstance(body, dict) else None
    if isinstance(error, dict):
        error = error.get("message")
    if not isinstance(error, str):
        error = body.get("message") if isinstance(body, dict) else None
    return error[:300] if isinstance(error, str) else ""


def classify_http_status(status: int) -> tuple[str, bool]:
    """Map an HTTP status from a provider to (error code, retryable)."""
    if status in (401, 403):
        return "provider_auth_failed", False
    if status == 429:
        return "provider_rate_limited", True
    if status >= 500:
        return "provider_unavailable", True
    return "provider_rejected_request", False
