"""Request bodies, validated with pydantic. Unknown fields are rejected."""

from __future__ import annotations

import uuid
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models import GenerationKind, ProjectStatus, Role


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


def _bounded_json(value: dict[str, Any], limit: int = 20_000) -> dict[str, Any]:
    import json

    if len(json.dumps(value, default=str)) > limit:
        raise ValueError(f"must be smaller than {limit} characters when encoded")
    return value


# ---- Auth ---------------------------------------------------------------------

class RegisterIn(Strict):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)
    display_name: str = Field(min_length=1, max_length=80)
    accept_terms: bool

    @field_validator("accept_terms")
    @classmethod
    def must_accept(cls, v: bool) -> bool:
        if not v:
            raise ValueError("You must accept the Terms of Service and Privacy Policy.")
        return v


class LoginIn(Strict):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class EmailIn(Strict):
    email: EmailStr


class TokenIn(Strict):
    token: str = Field(min_length=10, max_length=200)


class ResetPasswordIn(Strict):
    token: str = Field(min_length=10, max_length=200)
    new_password: str = Field(min_length=1, max_length=128)


class ChangePasswordIn(Strict):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=1, max_length=128)


class DeleteAccountIn(Strict):
    password: str = Field(min_length=1, max_length=128)
    confirm: str

    @field_validator("confirm")
    @classmethod
    def must_confirm(cls, v: str) -> str:
        if v != "DELETE":
            raise ValueError('Type DELETE to confirm.')
        return v


class ProfileUpdateIn(Strict):
    display_name: str | None = Field(default=None, min_length=1, max_length=80)
    preferred_language: str | None = Field(default=None, max_length=16)
    country: str | None = Field(default=None, min_length=2, max_length=2)


# ---- Projects -------------------------------------------------------------------

class ProjectCreateIn(Strict):
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=10_000)
    brief: dict[str, Any] = Field(default_factory=dict)

    @field_validator("brief")
    @classmethod
    def brief_size(cls, v: dict[str, Any]) -> dict[str, Any]:
        return _bounded_json(v)


class ProjectUpdateIn(Strict):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=10_000)
    status: ProjectStatus | None = None
    brief: dict[str, Any] | None = None

    @field_validator("brief")
    @classmethod
    def brief_size(cls, v: dict[str, Any] | None) -> dict[str, Any] | None:
        return v if v is None else _bounded_json(v)


class CharacterIn(Strict):
    name: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", max_length=5_000)
    traits: dict[str, Any] = Field(default_factory=dict)
    reference_asset_id: uuid.UUID | None = None

    @field_validator("traits")
    @classmethod
    def traits_size(cls, v: dict[str, Any]) -> dict[str, Any]:
        return _bounded_json(v, 5_000)


class CharacterUpdateIn(Strict):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=5_000)
    traits: dict[str, Any] | None = None
    reference_asset_id: uuid.UUID | None = None

    @field_validator("traits")
    @classmethod
    def traits_size(cls, v: dict[str, Any] | None) -> dict[str, Any] | None:
        return v if v is None else _bounded_json(v, 5_000)


class SceneIn(Strict):
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=10_000)
    shot_notes: str = Field(default="", max_length=5_000)
    dialogue: str = Field(default="", max_length=10_000)
    duration_seconds: int | None = Field(default=None, ge=1, le=3600)
    character_ids: list[uuid.UUID] = Field(default_factory=list, max_length=50)
    preview_asset_id: uuid.UUID | None = None


class SceneUpdateIn(Strict):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=10_000)
    shot_notes: str | None = Field(default=None, max_length=5_000)
    dialogue: str | None = Field(default=None, max_length=10_000)
    duration_seconds: int | None = Field(default=None, ge=1, le=3600)
    character_ids: list[uuid.UUID] | None = Field(default=None, max_length=50)
    preview_asset_id: uuid.UUID | None = None


class SceneOrderIn(Strict):
    scene_ids: list[uuid.UUID] = Field(max_length=500)


class AssetUpdateIn(Strict):
    display_name: str | None = Field(default=None, min_length=1, max_length=255)
    project_id: uuid.UUID | None = None


# ---- Generation ---------------------------------------------------------------------

class GenerationIn(Strict):
    provider: str = Field(min_length=1, max_length=50)
    model: str = Field(min_length=1, max_length=100)
    kind: GenerationKind
    params: dict[str, Any] = Field(default_factory=dict)
    project_id: uuid.UUID | None = None
    scene_id: uuid.UUID | None = None

    @field_validator("params")
    @classmethod
    def params_size(cls, v: dict[str, Any]) -> dict[str, Any]:
        return _bounded_json(v, 30_000)


class QuoteIn(Strict):
    provider: str = Field(min_length=1, max_length=50)
    model: str = Field(min_length=1, max_length=100)
    kind: GenerationKind
    params: dict[str, Any] = Field(default_factory=dict)


# ---- Billing ------------------------------------------------------------------------

class CheckoutIn(Strict):
    """Only WHAT to buy. Prices, currency and credits come from the server's catalog, so
    fields like amount or currency are rejected as unknown (extra="forbid")."""
    item_type: Literal["credit_package", "subscription"]
    item_code: str = Field(min_length=1, max_length=50, pattern=r"^[a-z0-9_]+$")


class PaymentReferenceIn(Strict):
    reference: str = Field(min_length=6, max_length=100, pattern=r"^[A-Za-z0-9.=-]+$")


# ---- Admin --------------------------------------------------------------------------

class AdminUserUpdateIn(Strict):
    is_active: bool | None = None
    role: Role | None = None


class AdminCreditIn(Strict):
    amount: int = Field(ge=-1_000_000, le=1_000_000)
    reason: str = Field(min_length=3, max_length=255)

    @field_validator("amount")
    @classmethod
    def non_zero(cls, v: int) -> int:
        if v == 0:
            raise ValueError("Amount must not be zero.")
        return v
