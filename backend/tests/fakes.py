"""Fake provider adapters for tests. They never touch the network."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models import AssetKind, GenerationKind
from app.providers.base import (
    JobContext,
    ModelSpec,
    ProviderAdapter,
    ProviderError,
    ProviderOutcome,
    ProviderOutput,
    SettingField,
)

MP4 = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 100


class TextParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    prompt: str = Field(min_length=1, max_length=2000)
    max_output_tokens: int = Field(default=1000, ge=100, le=4000)


class FakeTextAdapter(ProviderAdapter):
    """Synchronous provider. Class attributes control its behaviour per test."""

    name = "fake-text"
    label = "Fake Text"
    credential_env = "FAKE_TEXT_KEY"
    configured = True
    errors: list[ProviderError] = []
    usage: dict[str, float] = {"input_tokens": 100, "output_tokens": 200}
    calls = 0

    @classmethod
    def reset(cls):
        cls.configured = True
        cls.errors = []
        cls.usage = {"input_tokens": 100, "output_tokens": 200}
        cls.calls = 0

    def is_configured(self) -> bool:
        return type(self).configured

    def model_specs(self) -> list[ModelSpec]:
        return [ModelSpec(id="fake-writer", label="Fake writer", kind=GenerationKind.TEXT,
                          description="test", params_model=TextParams,
                          fields=[SettingField("prompt", "Prompt", "textarea", required=True)],
                          usage_metrics=["input_tokens", "output_tokens"])]

    def estimate_usage(self, model: ModelSpec, params: dict[str, Any]) -> dict[str, float]:
        return {"input_tokens": 500, "output_tokens": params["max_output_tokens"]}

    def submit(self, ctx: JobContext) -> ProviderOutcome:
        type(self).calls += 1
        if type(self).errors:
            raise type(self).errors.pop(0)
        text = f"Draft for: {ctx.params['prompt']}"
        return ProviderOutcome(
            status="completed", result={"text": text},
            outputs=[ProviderOutput(kind=AssetKind.TEXT, mime_type="text/markdown",
                                    display_name="Draft.md", data=text.encode())],
            usage=dict(type(self).usage))


class VideoParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    prompt_text: str = Field(min_length=1, max_length=1000)
    duration: int = Field(default=5, ge=2, le=10)
    reference_asset_id: str | None = None


class FakeAsyncVideoAdapter(ProviderAdapter):
    """Asynchronous provider: submit returns a task ID; poll finishes after N calls."""

    name = "fake-video"
    label = "Fake Video"
    supports_cancel = True
    credential_env = "FAKE_VIDEO_KEY"
    polls_until_done = 2
    final: Literal["succeed", "fail"] = "succeed"
    poll_calls = 0
    cancelled: list[str] = []
    stay_pending = False

    @classmethod
    def reset(cls):
        cls.polls_until_done = 2
        cls.final = "succeed"
        cls.poll_calls = 0
        cls.cancelled = []
        cls.stay_pending = False

    def is_configured(self) -> bool:
        return True

    def model_specs(self) -> list[ModelSpec]:
        return [ModelSpec(id="fake-motion", label="Fake motion", kind=GenerationKind.VIDEO,
                          description="test", params_model=VideoParams, fields=[],
                          usage_metrics=["video_seconds"])]

    def estimate_usage(self, model: ModelSpec, params: dict[str, Any]) -> dict[str, float]:
        return {"video_seconds": params["duration"]}

    def submit(self, ctx: JobContext) -> ProviderOutcome:
        if ctx.params.get("reference_asset_id"):
            import uuid

            data, mime = ctx.load_asset(uuid.UUID(ctx.params["reference_asset_id"]))
            assert data and mime.startswith("image/")
        return ProviderOutcome(status="pending", provider_job_id=f"task-{ctx.job_id}", progress=0)

    def poll(self, ctx: JobContext) -> ProviderOutcome:
        cls = type(self)
        cls.poll_calls += 1
        if cls.stay_pending or cls.poll_calls < cls.polls_until_done:
            return ProviderOutcome(status="pending", provider_job_id=ctx.provider_job_id, progress=50)
        if cls.final == "fail":
            raise ProviderError("The fake provider failed.", code="fake_failed")
        return ProviderOutcome(
            status="completed", provider_job_id=ctx.provider_job_id,
            outputs=[ProviderOutput(kind=AssetKind.VIDEO, mime_type="video/mp4", display_name="Clip",
                                    data=MP4, duration_seconds=ctx.params["duration"])],
            usage={"video_seconds": ctx.params["duration"]})

    def cancel(self, ctx: JobContext) -> bool:
        type(self).cancelled.append(ctx.provider_job_id)
        return True
