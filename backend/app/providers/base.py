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
from typing import Any, Literal

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
    usage:     anything the provider says it billed despite the failure, so the
               user is charged only for usage that really happened.
    """

    def __init__(self, message: str, *, code: str = "provider_error", retryable: bool = False,
                 usage: dict[str, float] | None = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.retryable = retryable
        self.usage = usage or {}


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

    @abstractmethod
    def is_configured(self) -> bool: ...

    @abstractmethod
    def model_specs(self) -> list[ModelSpec]: ...

    def get_model(self, model_id: str) -> ModelSpec | None:
        return next((m for m in self.model_specs() if m.id == model_id), None)

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


def classify_http_status(status: int) -> tuple[str, bool]:
    """Map an HTTP status from a provider to (error code, retryable)."""
    if status in (401, 403):
        return "provider_auth_failed", False
    if status == 429:
        return "provider_rate_limited", True
    if status >= 500:
        return "provider_unavailable", True
    return "provider_rejected_request", False
