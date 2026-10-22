"""OpenAI adapter: text-to-speech (POST https://api.openai.com/v1/audio/speech) and image
generation (see openai_image.py).

Request fields, model IDs, voices, formats and the 4096-character limit were
checked against the official openai-python SDK source (generated from OpenAI's
API spec) on 2026-10-21; see docs/PROVIDERS.md. Credential: OPENAI_API_KEY.
Usage metric: characters.

Model status (OpenAI deprecations page and text-to-speech guide, read through search
summaries on 2026-10-22; re-check on the live pages): tts-1, tts-1-hd and gpt-4o-mini-tts
are all deprecated, with shutdown on 2027-01-06. OpenAI's suggested replacement
(gpt-realtime-2.1-mini) uses the Realtime API, not /v1/audio/speech, so it is not a drop-in
model swap and is not implemented here. From the shutdown date these models are refused
instead of failing at OpenAI.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Literal

import httpx
from flask import current_app
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models import AssetKind, GenerationKind
from app.providers import openai_image
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
    "gpt-4o-mini-tts": "Recommended. Natural voices; accepts speaking-style instructions.",
    "tts-1": "Fast, lower latency. Fewer voices.",
    "tts-1-hd": "Higher quality, slower. Fewer voices.",
}
SHUTDOWN_ON = date(2027, 1, 6)
DEPRECATION_NOTE = ("OpenAI has deprecated this voice model; it stops working on 6 January 2027.")
VOICES = ["alloy", "ash", "ballad", "coral", "echo", "sage", "shimmer", "verse", "marin",
          "cedar", "fable", "onyx", "nova"]
# tts-1 and tts-1-hd support fewer voices than gpt-4o-mini-tts (createSpeech reference).
LEGACY_VOICES = ["alloy", "ash", "coral", "echo", "fable", "onyx", "nova", "sage", "shimmer"]
LEGACY_MODELS = ("tts-1", "tts-1-hd")


def voices_for(model_id: str) -> list[str]:
    return LEGACY_VOICES if model_id in LEGACY_MODELS else VOICES


def default_voice(model_id: str) -> str:
    return "alloy" if model_id in LEGACY_MODELS else "marin"
FORMATS = {"mp3": "audio/mpeg", "wav": "audio/wav", "opus": "audio/opus", "aac": "audio/aac",
           "flac": "audio/flac"}


class SpeechParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_id: str = Field(exclude=True, default="")
    text: str = Field(min_length=1, max_length=4096)
    voice: Literal["alloy", "ash", "ballad", "coral", "echo", "sage", "shimmer", "verse", "marin",
                   "cedar", "fable", "onyx", "nova"] | None = None
    response_format: Literal["mp3", "wav", "opus", "aac", "flac"] = "mp3"
    speed: float = Field(default=1.0, ge=0.25, le=4.0)
    instructions: str | None = Field(default=None, max_length=1000)
    language: str | None = Field(default=None, max_length=40)

    @model_validator(mode="after")
    def model_support(self):
        if self.voice is None:
            self.voice = default_voice(self.model_id)
        if self.voice not in voices_for(self.model_id):
            raise ValueError(f"{self.model_id} does not offer the voice '{self.voice}'. "
                             f"Choose one of: {', '.join(voices_for(self.model_id))}.")
        if (self.instructions or self.language) and self.model_id in LEGACY_MODELS:
            raise ValueError("Speaking style and language hints only work with gpt-4o-mini-tts.")
        return self


def _fields(model_id: str) -> list[SettingField]:
    fields = [
        SettingField("text", "Text to speak", "textarea", required=True, max_length=4096),
        SettingField("voice", "Voice", "select", default=default_voice(model_id),
                     options=[{"value": v, "label": v.capitalize()} for v in voices_for(model_id)],
                     help="Marin and Cedar are OpenAI's recommended voices." if model_id not in LEGACY_MODELS
                     else None),
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


class OpenAIAdapter(ProviderAdapter):
    """OpenAI: text-to-speech (/v1/audio/speech) and image generation (/v1/images/generations)."""

    name = "openai"
    label = "OpenAI"
    credential_env = "OPENAI_API_KEY"
    default_model_settings = {GenerationKind.SPEECH: "OPENAI_TTS_MODEL",
                              GenerationKind.IMAGE: "OPENAI_IMAGE_MODEL"}
    connection_test = ("Reads the model information of the default voice and image models "
                       "(GET /v1/models/{model}). Nothing is generated.")

    def is_configured(self) -> bool:
        return bool(current_app.config.get("OPENAI_API_KEY"))

    def model_specs(self) -> list[ModelSpec]:
        return [
            ModelSpec(id=mid, label=mid, kind=GenerationKind.SPEECH, description=desc,
                      params_model=SpeechParams, fields=_fields(mid), usage_metrics=["characters"],
                      deprecated=DEPRECATION_NOTE, shutdown_on=SHUTDOWN_ON)
            for mid, desc in MODELS.items()
        ] + openai_image.image_specs()

    def validate(self, model: ModelSpec, raw: dict[str, Any]) -> dict[str, Any]:
        if model.kind == GenerationKind.IMAGE:
            return super().validate(model, raw)
        data = dict(raw)
        data["model_id"] = model.id
        params = SpeechParams.model_validate(data).model_dump(mode="json", exclude_none=True)
        return params

    def estimate_usage(self, model: ModelSpec, params: dict[str, Any]) -> dict[str, float]:
        if model.kind == GenerationKind.IMAGE:
            return openai_image.estimate_usage(params)
        return {"characters": len(params["text"])}

    def params_for_brief(self, model: ModelSpec, brief: dict[str, Any]) -> dict[str, Any]:
        if model.kind == GenerationKind.IMAGE:
            prompt = " ".join(x for x in (brief.get("prompt"), brief.get("style")) if x)[:4000]
            size = "1024x1536" if brief.get("orientation") == "portrait" else "1536x1024"
            return {"prompt": prompt, "size": size, "quality": "medium", "output_format": "png"}
        return {"text": (brief.get("text") or "")[:4096], "voice": default_voice(model.id)}

    def test_connection(self) -> str:
        checked = []
        for kind in (GenerationKind.SPEECH, GenerationKind.IMAGE):
            spec = self.default_model(kind)
            if spec is None:
                continue
            try:
                response = httpx.get(f"https://api.openai.com/v1/models/{spec.id}", timeout=20.0,
                                     headers={"Authorization": f"Bearer {current_app.config['OPENAI_API_KEY']}"})
            except httpx.HTTPError as exc:
                raise ProviderError("OpenAI could not be reached.", code="provider_unavailable") from exc
            if response.status_code == 404:
                raise ProviderError(f"The key works, but model '{spec.id}' is not available to it.",
                                    code="model_unavailable")
            if response.status_code != 200:
                code, _ = classify_http_status(response.status_code)
                raise ProviderError(f"OpenAI answered {response.status_code}.", code=code)
            checked.append(spec.id)
        return "Credential accepted; models available: " + ", ".join(checked)

    def submit(self, ctx: JobContext) -> ProviderOutcome:
        spec = self.get_model(ctx.model)
        if spec is not None and spec.kind == GenerationKind.IMAGE:
            return openai_image.submit(ctx)
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


# Kept for code that still imports the old name.
OpenAISpeechAdapter = OpenAIAdapter
