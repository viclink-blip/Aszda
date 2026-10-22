"""OpenAI image generation (POST https://api.openai.com/v1/images/generations).

Used by the OpenAI adapter (openai_speech.py). Model IDs and request fields were checked
against the official openai-python SDK (generated from OpenAI's API spec), version 3.36.1,
on 2026-10-22: GPT image models always return base64 images (`data[].b64_json`), accept
`size` 1024x1024 / 1536x1024 / 1024x1536 (all GPT image models), `quality` low/medium/high,
`output_format` png/jpeg/webp and `background` auto/opaque/transparent, and report token
`usage`. DALL-E models were retired on 2026-05-12 and are not offered.

Credits: images are priced per image and quality (usage metrics images_low, images_medium,
images_high). OpenAI bills by tokens; the token usage it reports is kept with each job so
provider costs can be reconciled. No per-image provider price is assumed here.
"""

from __future__ import annotations

import base64
import binascii
from typing import Any, Literal

import httpx
from flask import current_app
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models import AssetKind, GenerationKind
from app.providers.base import (
    JobContext,
    ModelSpec,
    ProviderError,
    ProviderOutcome,
    ProviderOutput,
    SettingField,
    classify_http_status,
)

ENDPOINT = "https://api.openai.com/v1/images/generations"
SIZES = {"1024x1024": "Square (1024×1024)", "1536x1024": "Landscape (1536×1024)",
         "1024x1536": "Portrait (1024×1536)"}
MIME = {"png": "image/png", "jpeg": "image/jpeg", "webp": "image/webp"}
MAX_IMAGE_BYTES = 50 * 1024 * 1024


class ImageParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: str = Field(min_length=1, max_length=4000)
    size: Literal["1024x1024", "1536x1024", "1024x1536"] = "1024x1024"
    quality: Literal["low", "medium", "high"] = "medium"
    output_format: Literal["png", "jpeg", "webp"] = "png"
    background: Literal["auto", "opaque", "transparent"] = "auto"

    @model_validator(mode="after")
    def transparent_needs_alpha(self):
        if self.background == "transparent" and self.output_format == "jpeg":
            raise ValueError("A transparent background needs PNG or WebP.")
        return self


FIELDS = [
    SettingField("prompt", "Describe the image", "textarea", required=True, max_length=4000,
                 help="Subject, setting, style, lighting and composition."),
    SettingField("size", "Size", "select", default="1024x1024",
                 options=[{"value": k, "label": v} for k, v in SIZES.items()]),
    SettingField("quality", "Quality", "select", default="medium",
                 options=[{"value": "low", "label": "Low (fastest, fewest credits)"},
                          {"value": "medium", "label": "Medium"},
                          {"value": "high", "label": "High (most credits)"}]),
    SettingField("output_format", "File format", "select", default="png",
                 options=[{"value": f, "label": f.upper()} for f in MIME]),
    SettingField("background", "Background", "select", default="auto",
                 options=[{"value": "auto", "label": "Automatic"}, {"value": "opaque", "label": "Opaque"},
                          {"value": "transparent", "label": "Transparent (PNG or WebP)"}]),
]

USAGE_METRICS = ["images_low", "images_medium", "images_high"]


def image_specs() -> list[ModelSpec]:
    return [
        ModelSpec(id=model_id, label=f"OpenAI {model_id}", kind=GenerationKind.IMAGE,
                  description="Images from a text description: characters, scenes, storyboards.",
                  params_model=ImageParams, fields=FIELDS, usage_metrics=USAGE_METRICS)
        for model_id in current_app.config["OPENAI_IMAGE_MODELS"]
    ]


def estimate_usage(params: dict[str, Any]) -> dict[str, float]:
    return {f"images_{params['quality']}": 1}


def submit(ctx: JobContext) -> ProviderOutcome:
    p = ctx.params
    body = {"model": ctx.model, "prompt": p["prompt"], "n": 1, "size": p["size"], "quality": p["quality"],
            "output_format": p["output_format"], "background": p["background"]}
    try:
        response = httpx.post(ENDPOINT, json=body, timeout=httpx.Timeout(300.0, connect=10.0),
                              headers={"Authorization": f"Bearer {current_app.config['OPENAI_API_KEY']}"})
    except httpx.HTTPError as exc:
        raise ProviderError("OpenAI could not be reached.", code="provider_unavailable", retryable=True) from exc
    if response.status_code != 200:
        error_code = None
        try:
            error_code = (response.json().get("error") or {}).get("code")
        except ValueError:
            pass
        if error_code == "moderation_blocked":  # OpenAI's image moderation error code
            raise ProviderError("OpenAI's safety system declined this image request. Your credits were "
                                "returned. Please change the description.", code="content_refused",
                                provider_reported={"error_code": error_code})
        code, retryable = classify_http_status(response.status_code)
        if response.status_code == 404:
            code = "model_unavailable"
        raise ProviderError(f"OpenAI returned an error ({response.status_code}).", code=code, retryable=retryable)

    data = response.json()
    images = [item.get("b64_json") for item in (data.get("data") or []) if isinstance(item, dict)]
    if not images or not images[0]:
        raise ProviderError("OpenAI returned no image.", code="empty_result")
    try:
        raw = base64.b64decode(images[0], validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ProviderError("OpenAI returned an unreadable image.", code="unexpected_provider_response") from exc
    if not raw or len(raw) > MAX_IMAGE_BYTES:
        raise ProviderError("OpenAI returned an unexpected image.", code="unexpected_provider_response")
    width, height = (int(v) for v in p["size"].split("x"))
    fmt = data.get("output_format") or p["output_format"]
    return ProviderOutcome(
        status="completed",
        outputs=[ProviderOutput(kind=AssetKind.IMAGE, mime_type=MIME.get(fmt, "image/png"),
                                display_name="Image", data=raw, width=width, height=height)],
        result={"size": p["size"], "quality": data.get("quality") or p["quality"], "format": fmt,
                # OpenAI's token usage for this image, for cost reconciliation.
                "provider_reported": {"usage": data.get("usage")} if data.get("usage") else None},
        usage=estimate_usage(p),
    )
