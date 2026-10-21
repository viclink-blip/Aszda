"""OpenAI text-to-speech adapter (POST https://api.openai.com/v1/audio/speech).

Request fields, model IDs, voices, formats and the 4096-character limit were
checked against the official openai-python SDK source (generated from OpenAI's
API spec) on 2026-10-21; see docs/PROVIDERS.md. Credential: OPENAI_API_KEY.
Usage metric: characters.
"""

from __future__ import annotations

from typing import Any, Literal

import httpx
from flask import current_app
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models import AssetKind, GenerationKind
from app.providers.base import (
    JobContext,
    ModelSpec,
    ProviderAdapter,
    ProviderError,
    ProviderOutcome,
    ProviderOutput,
    SettingField,
    classify_http_status,
)

ENDPOINT = "https://api.openai.com/v1/audio/speech"
MODELS = {
    "gpt-4o-mini-tts": "Natural voices; accepts speaking-style instructions.",
    "tts-1": "Fast, lower latency.",
    "tts-1-hd": "Higher quality, slower.",
}
VOICES = ["alloy", "ash", "ballad", "coral", "echo", "sage", "shimmer", "verse", "marin",
          "cedar", "fable", "onyx", "nova"]
FORMATS = {"mp3": "audio/mpeg", "wav": "audio/wav", "opus": "audio/opus", "aac": "audio/aac",
           "flac": "audio/flac"}


class SpeechParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_id: str = Field(exclude=True, default="")
    text: str = Field(min_length=1, max_length=4096)
    voice: Literal["alloy", "ash", "ballad", "coral", "echo", "sage", "shimmer", "verse", "marin",
                   "cedar", "fable", "onyx", "nova"] = "marin"
    response_format: Literal["mp3", "wav", "opus", "aac", "flac"] = "mp3"
    speed: float = Field(default=1.0, ge=0.25, le=4.0)
    instructions: str | None = Field(default=None, max_length=1000)
    language: str | None = Field(default=None, max_length=40)

    @model_validator(mode="after")
    def instructions_supported(self):
        if self.instructions and self.model_id in ("tts-1", "tts-1-hd"):
            raise ValueError("Speaking instructions only work with gpt-4o-mini-tts.")
        return self


def _fields(model_id: str) -> list[SettingField]:
    fields = [
        SettingField("text", "Text to speak", "textarea", required=True, max_length=4096),
        SettingField("voice", "Voice", "select", default="marin",
                     options=[{"value": v, "label": v.capitalize()} for v in VOICES],
                     help="OpenAI notes that voice availability can differ by model; "
                          "marin and cedar are its recommended voices."),
        SettingField("response_format", "Audio format", "select", default="mp3",
                     options=[{"value": f, "label": f.upper()} for f in FORMATS]),
        SettingField("speed", "Speed", "number", minimum=0.25, maximum=4.0, default=1.0),
    ]
    if model_id == "gpt-4o-mini-tts":
        fields.append(SettingField(
            "instructions", "Speaking style", "textarea", max_length=1000,
            help="For example: warm and calm narrator, slight excitement at the end.",
        ))
        fields.append(SettingField(
            "language", "Language (hint)", "text", max_length=40,
            help="The voice follows the language of your text. This hint is added to the speaking "
                 "style instructions.",
        ))
    return fields


class OpenAISpeechAdapter(ProviderAdapter):
    name = "openai"
    label = "OpenAI Text-to-Speech"
    credential_env = "OPENAI_API_KEY"

    def is_configured(self) -> bool:
        return bool(current_app.config.get("OPENAI_API_KEY"))

    def model_specs(self) -> list[ModelSpec]:
        return [
            ModelSpec(id=mid, label=mid, kind=GenerationKind.SPEECH, description=desc,
                      params_model=SpeechParams, fields=_fields(mid), usage_metrics=["characters"])
            for mid, desc in MODELS.items()
        ]

    def validate(self, model: ModelSpec, raw: dict[str, Any]) -> dict[str, Any]:
        data = dict(raw)
        data["model_id"] = model.id
        params = SpeechParams.model_validate(data).model_dump(mode="json", exclude_none=True)
        return params

    def estimate_usage(self, model: ModelSpec, params: dict[str, Any]) -> dict[str, float]:
        return {"characters": len(params["text"])}

    def submit(self, ctx: JobContext) -> ProviderOutcome:
        p = ctx.params
        body: dict[str, Any] = {
            "model": ctx.model, "input": p["text"], "voice": p["voice"],
            "response_format": p["response_format"], "speed": p["speed"],
        }
        instructions = p.get("instructions") or ""
        if p.get("language") and ctx.model == "gpt-4o-mini-tts":
            instructions = f"{instructions}\nSpeak in {p['language']}.".strip()
        if instructions:
            body["instructions"] = instructions
        try:
            response = httpx.post(
                ENDPOINT, json=body, timeout=httpx.Timeout(120.0, connect=10.0),
                headers={"Authorization": f"Bearer {current_app.config['OPENAI_API_KEY']}"},
            )
        except httpx.HTTPError as exc:
            raise ProviderError("OpenAI could not be reached.", code="provider_unavailable",
                                retryable=True) from exc
        if response.status_code != 200:
            code, retryable = classify_http_status(response.status_code)
            raise ProviderError(f"OpenAI returned an error ({response.status_code}).", code=code,
                                retryable=retryable)
        if not response.content:
            raise ProviderError("OpenAI returned empty audio.", code="empty_result")
        mime = FORMATS[p["response_format"]]
        return ProviderOutcome(
            status="completed",
            outputs=[ProviderOutput(kind=AssetKind.AUDIO, mime_type=mime,
                                    display_name=f"Voice - {p['voice']}", data=response.content)],
            result={"voice": p["voice"], "format": p["response_format"]},
            usage={"characters": len(p["text"])},
        )
