"""Anthropic Claude adapter for text work: story concepts, scripts, characters, scene breakdowns.

Uses the official `anthropic` Python SDK (Messages API). Credential: ANTHROPIC_API_KEY.
Usage metrics: input_tokens, output_tokens (as reported by the API).
"""

from __future__ import annotations

from typing import Any, Literal

import anthropic
from flask import current_app
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

# Models that accept the server-side refusal fallback (`fallbacks: "default"`).
_FALLBACK_MODELS = {"claude-opus-5-5", "claude-opus-5", "claude-fable-5-1", "claude-sonnet-5-5"}
_FALLBACK_BETA = "server-side-fallback-2026-07-01"

TASKS: dict[str, tuple[str, str]] = {
    "story_concept": (
        "Story concept",
        "You are a story development partner inside ASZDA Studio, a tool for creators making short "
        "videos, ads, animated stories and films. Develop the user's idea into a clear concept: a "
        "logline, the premise, tone and genre, the main characters, and three possible directions. "
        "Use Markdown headings. Keep it practical for a small production.",
    ),
    "script": (
        "Script draft",
        "You are a screenwriter inside ASZDA Studio. Write a script draft from the user's idea, in "
        "standard screenplay structure (scene headings, action, character names, dialogue) using "
        "plain Markdown. Keep scenes short and visual, suitable for AI video generation.",
    ),
    "characters": (
        "Character sheet",
        "You are a character designer inside ASZDA Studio. Propose the characters the user's story "
        "needs. For each: name, role, visual appearance (specific enough to keep a consistent look "
        "across generated images and videos), personality, and voice. Use Markdown.",
    ),
    "scene_breakdown": (
        "Scene breakdown",
        "You are a director and storyboard artist inside ASZDA Studio. Break the user's story into "
        "numbered scenes. For each scene give: a title, what happens, the shot (framing, camera "
        "movement), which characters appear, any dialogue, and a suggested length in seconds. "
        "Use Markdown.",
    ),
    "freeform": (
        "Free prompt",
        "You are a creative assistant inside ASZDA Studio, helping people plan visual and audio "
        "content. Answer clearly and practically. Use Markdown when it helps.",
    ),
}


class TextParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task: Literal["story_concept", "script", "characters", "scene_breakdown", "freeform"] = "freeform"
    prompt: str = Field(min_length=1, max_length=12000)
    max_output_tokens: int = Field(default=4000, ge=500, le=16000)
    effort: Literal["low", "medium", "high"] = "medium"


FIELDS = [
    SettingField("task", "What do you need?", "select", required=True, default="story_concept",
                 options=[{"value": k, "label": v[0]} for k, v in TASKS.items()]),
    SettingField("prompt", "Your idea", "textarea", required=True, max_length=12000,
                 help="Describe the story, audience, tone and anything that must be included."),
    SettingField("max_output_tokens", "Maximum length (tokens)", "integer", minimum=500, maximum=16000,
                 default=4000, help="An upper limit. Credits are reserved for this limit and the "
                                    "unused part is returned."),
    SettingField("effort", "Thinking effort", "select", default="medium",
                 options=[{"value": "low", "label": "Low (faster)"},
                          {"value": "medium", "label": "Medium"},
                          {"value": "high", "label": "High (more thorough)"}]),
]


class AnthropicTextAdapter(ProviderAdapter):
    name = "anthropic"
    label = "Anthropic Claude"
    credential_env = "ANTHROPIC_API_KEY"

    def is_configured(self) -> bool:
        return bool(current_app.config.get("ANTHROPIC_API_KEY"))

    def model_specs(self) -> list[ModelSpec]:
        return [
            ModelSpec(
                id=model_id, label=f"Claude ({model_id})", kind=GenerationKind.TEXT,
                description="Story development, scripts, character sheets and scene breakdowns.",
                params_model=TextParams, fields=FIELDS, usage_metrics=["input_tokens", "output_tokens"],
            )
            for model_id in current_app.config["ANTHROPIC_TEXT_MODELS"]
        ]

    def estimate_usage(self, model: ModelSpec, params: dict[str, Any]) -> dict[str, float]:
        system = TASKS[params["task"]][1]
        # Roughly 4 characters per token; dividing by 2 gives a safe upper bound.
        input_tokens = (len(system) + len(params["prompt"])) // 2 + 100
        # max_tokens caps all output, including thinking, so it is a hard upper bound.
        return {"input_tokens": input_tokens, "output_tokens": params["max_output_tokens"]}

    def _client(self) -> anthropic.Anthropic:
        return anthropic.Anthropic(api_key=current_app.config["ANTHROPIC_API_KEY"], timeout=600.0,
                                   max_retries=2)

    def submit(self, ctx: JobContext) -> ProviderOutcome:
        params = ctx.params
        title, system = TASKS[params["task"]]
        kwargs: dict[str, Any] = {
            "model": ctx.model,
            "max_tokens": params["max_output_tokens"],
            "system": system,
            "messages": [{"role": "user", "content": params["prompt"]}],
            "output_config": {"effort": params["effort"]},
        }
        if ctx.model in _FALLBACK_MODELS:
            # If a safety classifier declines the request, Anthropic retries it on its
            # recommended fallback model server-side instead of returning a refusal.
            kwargs["betas"] = [_FALLBACK_BETA]
            kwargs["fallbacks"] = "default"
        try:
            response = self._client().beta.messages.create(**kwargs)
        except (anthropic.RateLimitError, anthropic.InternalServerError,
                anthropic.APITimeoutError, anthropic.APIConnectionError) as exc:
            raise ProviderError("Claude is busy or unreachable right now.",
                                code="provider_unavailable", retryable=True) from exc
        except (anthropic.AuthenticationError, anthropic.PermissionDeniedError) as exc:
            raise ProviderError("The Anthropic credential was rejected.",
                                code="provider_auth_failed") from exc
        except anthropic.APIStatusError as exc:
            raise ProviderError(f"Claude rejected the request ({exc.status_code}).",
                                code="provider_rejected_request") from exc

        usage = {"input_tokens": response.usage.input_tokens or 0,
                 "output_tokens": response.usage.output_tokens or 0}
        if response.stop_reason == "refusal":
            raise ProviderError("Claude declined this request. Try rephrasing it.",
                                code="content_refused", usage=usage)

        text = "".join(block.text for block in response.content if block.type == "text").strip()
        if not text:
            raise ProviderError("Claude returned no text.", code="empty_result", usage=usage)
        truncated = response.stop_reason == "max_tokens"
        return ProviderOutcome(
            status="completed",
            result={"text": text, "title": title, "truncated": truncated, "model": response.model,
                    "stop_reason": response.stop_reason},
            outputs=[ProviderOutput(kind=AssetKind.TEXT, mime_type="text/markdown",
                                    display_name=f"{title}.md", data=text.encode("utf-8"))],
            usage=usage,
        )
