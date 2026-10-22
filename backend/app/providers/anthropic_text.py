"""Anthropic Claude adapter for text work: story concepts, scripts, characters, scene breakdowns.

Uses the official `anthropic` Python SDK (Messages API). Credential: ANTHROPIC_API_KEY.
Usage metrics: input_tokens, output_tokens (as reported by the API).
"""

from __future__ import annotations

import json
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
    "director_plan": (
        "Film plan",
        "You are the AI Film Director inside ASZDA Studio. Turn the user's idea into a production "
        "plan for a short film made with AI image, video and voice generation. Give the film a title, "
        "a one-sentence logline and a visual style. List the characters with a visual description "
        "specific enough to keep them consistent across generated images and videos, and a voice "
        "description. Break the story into 3 to 12 scenes in order. For each scene write: a short "
        "title, what happens, the shot (framing and camera movement), any spoken dialogue, any "
        "narration, a length between 4 and 10 seconds, a self-contained image prompt for the key "
        "frame, a self-contained video prompt describing motion and sound, and the names of the "
        "characters who appear. Prompts must not depend on earlier scenes to be understood.",
    ),
    "freeform": (
        "Free prompt",
        "You are a creative assistant inside ASZDA Studio, helping people plan visual and audio "
        "content. Answer clearly and practically. Use Markdown when it helps.",
    ),
}


def _object(properties: dict[str, Any]) -> dict[str, Any]:
    return {"type": "object", "properties": properties, "required": list(properties),
            "additionalProperties": False}


# Structured output for the AI Film Director (output_config.format). Numeric limits are not
# supported in these schemas, so scene lengths are clamped after parsing.
DIRECTOR_PLAN_SCHEMA = _object({
    "title": {"type": "string"},
    "logline": {"type": "string"},
    "style": {"type": "string"},
    "characters": {"type": "array", "items": _object({
        "name": {"type": "string"}, "description": {"type": "string"}, "voice": {"type": "string"}})},
    "scenes": {"type": "array", "items": _object({
        "title": {"type": "string"}, "description": {"type": "string"}, "shot": {"type": "string"},
        "dialogue": {"type": "string"}, "narration": {"type": "string"},
        "duration_seconds": {"type": "integer"}, "image_prompt": {"type": "string"},
        "video_prompt": {"type": "string"}, "characters": {"type": "array", "items": {"type": "string"}}})},
})


def clean_plan(plan: dict[str, Any]) -> dict[str, Any]:
    """Clamp and trim a parsed plan so it fits ASZDA's storyboard limits."""
    scenes = []
    for scene in (plan.get("scenes") or [])[:12]:
        scene = dict(scene)
        scene["duration_seconds"] = min(10, max(4, int(scene.get("duration_seconds") or 6)))
        scene["title"] = (scene.get("title") or "Scene")[:120]
        scenes.append(scene)
    return {**plan, "title": (plan.get("title") or "Untitled film")[:120],
            "characters": (plan.get("characters") or [])[:20], "scenes": scenes}


def plan_markdown(plan: dict[str, Any]) -> str:
    lines = [f"# {plan['title']}", "", plan.get("logline", ""), "", f"**Style:** {plan.get('style', '')}", "",
             "## Characters"]
    lines += [f"- **{c.get('name')}**: {c.get('description')} (voice: {c.get('voice')})" for c in plan["characters"]]
    lines += ["", "## Scenes"]
    for i, s in enumerate(plan["scenes"], 1):
        lines += [f"### {i}. {s['title']} ({s['duration_seconds']} s)", s.get("description", ""),
                  f"*Shot:* {s.get('shot', '')}"]
        if s.get("dialogue"):
            lines.append(f"*Dialogue:* {s['dialogue']}")
        if s.get("narration"):
            lines.append(f"*Narration:* {s['narration']}")
        lines.append("")
    return "\n".join(lines)


class TextParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task: Literal["story_concept", "script", "characters", "scene_breakdown", "director_plan",
                  "freeform"] = "freeform"
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
    connection_test = ("Reads the model information of the configured Claude models (GET /v1/models/{id}). "
                       "Nothing is generated.")

    def params_for_brief(self, model: ModelSpec, brief: dict[str, Any]) -> dict[str, Any]:
        return {"task": "freeform", "prompt": (brief.get("prompt") or "")[:12000]}

    def test_connection(self) -> str:
        client = self._client().with_options(timeout=20.0, max_retries=0)
        found = []
        for spec in self.model_specs():
            try:
                info = client.models.retrieve(spec.id)
            except anthropic.NotFoundError as exc:
                raise ProviderError(f"The key works, but model '{spec.id}' is not available.",
                                    code="model_unavailable") from exc
            except (anthropic.AuthenticationError, anthropic.PermissionDeniedError) as exc:
                raise ProviderError("The Anthropic credential was rejected.", code="provider_auth_failed") from exc
            except (anthropic.APIConnectionError, anthropic.APITimeoutError) as exc:
                raise ProviderError("Anthropic could not be reached.", code="provider_unavailable") from exc
            except anthropic.APIStatusError as exc:
                raise ProviderError(f"Anthropic answered {exc.status_code}.", code="provider_error") from exc
            found.append(info.id)
        return "Credential accepted; models available: " + ", ".join(found)

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
        output_config: dict[str, Any] = {"effort": params["effort"]}
        if params["task"] == "director_plan":
            output_config["format"] = {"type": "json_schema", "schema": DIRECTOR_PLAN_SCHEMA}
        kwargs: dict[str, Any] = {
            "model": ctx.model,
            "max_tokens": params["max_output_tokens"],
            "system": system,
            "messages": [{"role": "user", "content": params["prompt"]}],
            "output_config": output_config,
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
        if params["task"] == "director_plan":
            try:
                plan = clean_plan(json.loads(text))
            except (ValueError, TypeError, AttributeError) as exc:
                # Usually a plan cut off by the length limit: the tokens were still used.
                raise ProviderError("Claude's plan was incomplete. Try a larger maximum length.",
                                    code="incomplete_plan", usage=usage) from exc
            markdown = plan_markdown(plan)
            return ProviderOutcome(
                status="completed",
                result={"plan": plan, "text": markdown, "title": title, "model": response.model,
                        "provider_reported": {"usage": usage},
                        "stop_reason": response.stop_reason},
                outputs=[ProviderOutput(kind=AssetKind.TEXT, mime_type="text/markdown",
                                        display_name=f"{plan['title'][:80]} - plan.md",
                                        data=markdown.encode("utf-8"))],
                usage=usage)
        return ProviderOutcome(
            status="completed",
            result={"text": text, "title": title, "truncated": truncated, "model": response.model,
                    "stop_reason": response.stop_reason, "provider_reported": {"usage": usage}},
            outputs=[ProviderOutput(kind=AssetKind.TEXT, mime_type="text/markdown",
                                    display_name=f"{title}.md", data=text.encode("utf-8"))],
            usage=usage,
        )
