"""Google image generation (Gemini image models, "Nano Banana") through the `google-genai` SDK.

Used by the Google adapter (google_video.py), with the same credentials (GEMINI_API_KEY, or
Vertex AI).

Imagen (models.generate_images) is not used: Google's deprecations page, read through search
summaries on 2026-10-28, lists the Imagen 4 models as shut down in the Gemini API on
2026-08-17, with Gemini image models as the replacement. Model IDs are NOT built in: set
ASZDA_GOOGLE_IMAGE_MODELS. On 2026-10-28 Google's pages (through search summaries) named
gemini-nano-banana-2.1 and gemini-3.1-flash-image; the admin connection test looks each
configured model up, so check it before pricing a model.

Checked against the SDK source (google-genai 2.32.0) on 2026-10-28:
- request: client.models.generate_content(model, contents=prompt,
  config=GenerateContentConfig(response_modalities=["IMAGE"],
  image_config=ImageConfig(aspect_ratio, image_size)));
- ImageConfig.aspect_ratio: "1:1", "2:3", "3:2", "3:4", "4:3", "9:16", "16:9", "21:9";
  image_size: "1K", "2K", "4K" (default 1K). person_generation and output_mime_type raise
  in Gemini API mode, so they are not offered;
- the image is a response part with inline_data (bytes + mime_type). Parts marked `thought`
  are the model's draft images and are skipped;
- refusals: prompt_feedback.block_reason, or a finish_reason such as IMAGE_SAFETY,
  IMAGE_PROHIBITED_CONTENT, SAFETY or PROHIBITED_CONTENT.

Credits: priced per image and size (usage metrics images_1k, images_2k, images_4k). Google
bills image output by tokens; the token usage it reports is kept with each job so provider
costs can be reconciled.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Literal

from flask import current_app
from pydantic import BaseModel, ConfigDict, Field

from app.models import AssetKind, GenerationKind
from app.providers.base import JobContext, ModelSpec, ProviderError, ProviderOutcome, ProviderOutput, SettingField

ASPECT_RATIOS = {"1:1": "Square 1:1", "16:9": "Landscape 16:9", "9:16": "Portrait 9:16",
                 "4:3": "Landscape 4:3", "3:4": "Portrait 3:4", "3:2": "Landscape 3:2",
                 "2:3": "Portrait 2:3", "21:9": "Cinema wide 21:9"}
MAX_IMAGE_BYTES = 50 * 1024 * 1024
REFUSED = {"SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST", "SPII", "RECITATION", "IMAGE_SAFETY",
           "IMAGE_PROHIBITED_CONTENT", "IMAGE_RECITATION"}


class GoogleImageParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: str = Field(min_length=1, max_length=4000)
    aspect_ratio: Literal["1:1", "16:9", "9:16", "4:3", "3:4", "3:2", "2:3", "21:9"] = "1:1"
    image_size: Literal["1K", "2K", "4K"] = "1K"


FIELDS = [
    SettingField("prompt", "Describe the image", "textarea", required=True, max_length=4000,
                 help="Subject, setting, style, lighting and composition."),
    SettingField("aspect_ratio", "Shape", "select", default="1:1",
                 options=[{"value": k, "label": v} for k, v in ASPECT_RATIOS.items()]),
    SettingField("image_size", "Resolution", "select", default="1K",
                 options=[{"value": "1K", "label": "1K (fewest credits)"}, {"value": "2K", "label": "2K"},
                          {"value": "4K", "label": "4K (most credits)"}]),
]

USAGE_METRICS = ["images_1k", "images_2k", "images_4k"]


def image_specs() -> list[ModelSpec]:
    return [
        ModelSpec(id=model_id, label=f"Google {model_id}", kind=GenerationKind.IMAGE,
                  description="Images from a text description: characters, scenes, storyboards.",
                  params_model=GoogleImageParams, fields=FIELDS, usage_metrics=USAGE_METRICS)
        for model_id in current_app.config.get("GOOGLE_IMAGE_MODELS", [])
    ]


def estimate_usage(params: dict[str, Any]) -> dict[str, float]:
    return {f"images_{params['image_size'].lower()}": 1}


def params_for_brief(brief: dict[str, Any]) -> dict[str, Any]:
    prompt = " ".join(x for x in (brief.get("prompt"), brief.get("style")) if x)[:4000]
    return {"prompt": prompt, "aspect_ratio": "9:16" if brief.get("orientation") == "portrait" else "16:9",
            "image_size": "1K"}


def _name(value: Any) -> str | None:
    if value is None:
        return None
    return str(getattr(value, "value", None) or getattr(value, "name", None) or value)


def submit(ctx: JobContext, client: Any, call: Callable[..., Any]) -> ProviderOutcome:
    from google.genai import types

    p = ctx.params
    config = types.GenerateContentConfig(
        response_modalities=["IMAGE"],
        image_config=types.ImageConfig(aspect_ratio=p["aspect_ratio"], image_size=p["image_size"]))
    response = call(client.models.generate_content, model=ctx.model, contents=p["prompt"], config=config)

    usage_metadata = getattr(response, "usage_metadata", None)
    reported = {"usage_metadata": usage_metadata.model_dump(mode="json", exclude_none=True)} \
        if hasattr(usage_metadata, "model_dump") else None
    refused = ProviderError(
        "Google's safety system declined this image request. Your credits were returned. Please "
        "change the description.", code="content_refused", provider_reported=reported)
    feedback = getattr(response, "prompt_feedback", None)
    if feedback is not None and getattr(feedback, "block_reason", None):
        raise refused

    candidates = getattr(response, "candidates", None) or []
    candidate = candidates[0] if candidates else None
    parts = getattr(getattr(candidate, "content", None), "parts", None) or []
    images = [part.inline_data for part in parts
              if getattr(part, "inline_data", None) is not None and not getattr(part, "thought", False)
              and (part.inline_data.mime_type or "").startswith("image/") and part.inline_data.data]
    if not images:
        if _name(getattr(candidate, "finish_reason", None)) in REFUSED:
            raise refused
        raise ProviderError("Google returned no image.", code="empty_result", provider_reported=reported)
    image = images[-1]  # the final image; earlier ones would be drafts
    if len(image.data) > MAX_IMAGE_BYTES:
        raise ProviderError("Google returned an unexpected image.", code="unexpected_provider_response")
    return ProviderOutcome(
        status="completed",
        outputs=[ProviderOutput(kind=AssetKind.IMAGE, mime_type=image.mime_type, display_name="Image",
                                data=image.data)],
        result={"aspect_ratio": p["aspect_ratio"], "image_size": p["image_size"], "provider_reported": reported},
        usage=estimate_usage(p),
    )
