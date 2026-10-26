"""Runway video generation adapter (https://api.dev.runwayml.com).

Endpoints, headers, model names, ratios and durations were checked against the
official runwayml Python SDK source (generated from Runway's API spec) on
2026-10-21; see docs/PROVIDERS.md. Credential: RUNWAYML_API_SECRET.

Runway jobs are asynchronous: submit() returns a task ID and poll() checks it
(Runway asks clients not to poll more often than every 5 seconds).
Usage metric: video_seconds.

Not verified: the exact shape of the create response. Runway's SDK reads an
`id` from it; if the response has no `id`, the job fails with a clear error
instead of guessing.
"""

from __future__ import annotations

import base64
import uuid
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
    out_of_credit,
    provider_error_text,
)

BASE_URL = "https://api.dev.runwayml.com"
API_VERSION = "2024-11-06"
MAX_PROMPT_IMAGE_BYTES = 5 * 1024 * 1024  # Runway's limit for base64 data URIs
MAX_OUTPUT_BYTES = 1024 * 1024 * 1024

GEN45_IMAGE_RATIOS = ["1280:720", "720:1280", "1104:832", "832:1104", "960:960", "1584:672"]
GEN45_TEXT_RATIOS = ["1280:720", "720:1280"]
VEO_RATIOS = ["1280:720", "720:1280", "1080:1920", "1920:1080"]

RATIO_LABELS = {
    "1280:720": "Landscape 16:9 (1280×720)", "720:1280": "Portrait 9:16 (720×1280)",
    "1104:832": "Landscape 4:3 (1104×832)", "832:1104": "Portrait 3:4 (832×1104)",
    "960:960": "Square (960×960)", "1584:672": "Cinematic 21:9 (1584×672)",
    "1080:1920": "Portrait 9:16 HD (1080×1920)", "1920:1080": "Landscape 16:9 HD (1920×1080)",
}


class _BaseVideoParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["text_to_video", "image_to_video"] = "text_to_video"
    prompt_text: str | None = Field(default=None, max_length=1000)
    reference_asset_id: uuid.UUID | None = None
    ratio: str
    seed: int | None = Field(default=None, ge=0, le=4294967295)

    @model_validator(mode="after")
    def check_mode(self):
        if self.mode == "image_to_video" and self.reference_asset_id is None:
            raise ValueError("Image-to-video needs a reference image.")
        if self.mode == "text_to_video":
            if not (self.prompt_text or "").strip():
                raise ValueError("Text-to-video needs a prompt.")
            self.reference_asset_id = None
        return self


class Gen45Params(_BaseVideoParams):
    duration: int = Field(default=5, ge=2, le=10)

    @model_validator(mode="after")
    def check_gen45(self):
        allowed = GEN45_TEXT_RATIOS if self.mode == "text_to_video" else GEN45_IMAGE_RATIOS
        if self.ratio not in allowed:
            raise ValueError(f"Ratio must be one of: {', '.join(allowed)}")
        if not (self.prompt_text or "").strip():
            raise ValueError("gen4.5 needs a prompt.")
        return self


class VeoParams(_BaseVideoParams):
    duration: Literal[4, 6, 8] = 8
    audio: bool = False

    @model_validator(mode="after")
    def check_veo(self):
        if self.ratio not in VEO_RATIOS:
            raise ValueError(f"Ratio must be one of: {', '.join(VEO_RATIOS)}")
        return self


def _ratio_options(values: list[str]) -> list[dict[str, str]]:
    return [{"value": v, "label": RATIO_LABELS[v]} for v in values]


_MODE_FIELD = SettingField(
    "mode", "Start from", "select", required=True, default="text_to_video",
    options=[{"value": "text_to_video", "label": "Text prompt"},
             {"value": "image_to_video", "label": "Reference image + prompt"}],
)
_IMAGE_FIELD = SettingField(
    "reference_asset_id", "Reference image", "asset", asset_kind="image",
    help="PNG, JPEG or WebP up to 5 MB. Used as the first frame.",
    show_when={"mode": ["image_to_video"]},
)
_SEED_FIELD = SettingField("seed", "Seed (optional)", "integer", minimum=0, maximum=4294967295,
                           help="Reuse a seed to get similar results.")

GEN45_FIELDS = [
    _MODE_FIELD,
    SettingField("prompt_text", "Prompt", "textarea", required=True, max_length=1000,
                 help="Describe the subject, action, camera movement and style."),
    _IMAGE_FIELD,
    SettingField("ratio", "Aspect ratio", "select", required=True, default="1280:720",
                 options=_ratio_options(GEN45_IMAGE_RATIOS),
                 help="Text-only generations support 16:9 and 9:16."),
    SettingField("duration", "Length (seconds)", "integer", minimum=2, maximum=10, default=5),
    _SEED_FIELD,
]

VEO_FIELDS = [
    _MODE_FIELD,
    SettingField("prompt_text", "Prompt", "textarea", max_length=1000,
                 help="Required for text-to-video; optional with a reference image."),
    _IMAGE_FIELD,
    SettingField("ratio", "Aspect ratio", "select", required=True, default="1280:720",
                 options=_ratio_options(VEO_RATIOS)),
    SettingField("duration", "Length (seconds)", "select", default="8",
                 options=[{"value": "4", "label": "4 seconds"}, {"value": "6", "label": "6 seconds"},
                          {"value": "8", "label": "8 seconds"}]),
    SettingField("audio", "Generate audio", "boolean", default=False),
    _SEED_FIELD,
]


class RunwayVideoAdapter(ProviderAdapter):
    name = "runway"
    label = "Runway"
    supports_cancel = True
    credential_env = "RUNWAYML_API_SECRET"
    default_model_settings = {GenerationKind.VIDEO: "RUNWAY_VIDEO_MODEL"}
    connection_test = ("Reads the organization's credit balance and usage tier (GET /v1/organization). "
                       "Nothing is generated.")

    def params_for_brief(self, model: ModelSpec, brief: dict[str, Any]) -> dict[str, Any]:
        portrait = brief.get("orientation") == "portrait"
        prompt = " ".join(x for x in (brief.get("prompt"), brief.get("style")) if x)[:1000]
        params: dict[str, Any] = {"prompt_text": prompt, "ratio": "720:1280" if portrait else "1280:720"}
        if brief.get("reference_asset_id"):
            params.update(mode="image_to_video", reference_asset_id=str(brief["reference_asset_id"]))
        else:
            params["mode"] = "text_to_video"
        seconds = int(brief.get("duration_seconds") or 5)
        if model.id == "veo3.1_fast":
            params["duration"] = min((4, 6, 8), key=lambda d: abs(d - seconds))
        else:
            params["duration"] = min(10, max(2, seconds))
        return params

    def test_connection(self) -> str:
        data = self._request("GET", "/v1/organization").json()
        balance = data.get("creditBalance") if isinstance(data, dict) else None
        return f"Credential accepted; Runway API credit balance: {balance}"

    def is_configured(self) -> bool:
        return bool(current_app.config.get("RUNWAY_API_KEY"))

    def model_specs(self) -> list[ModelSpec]:
        return [
            ModelSpec(id="gen4.5", label="Runway Gen-4.5", kind=GenerationKind.VIDEO,
                      description="Video from a text prompt or a reference image, 2–10 seconds.",
                      params_model=Gen45Params, fields=GEN45_FIELDS, usage_metrics=["video_seconds"]),
            ModelSpec(id="veo3.1_fast", label="Veo 3.1 Fast (via Runway)", kind=GenerationKind.VIDEO,
                      description="Video from text or an image, 4/6/8 seconds, optional audio.",
                      params_model=VeoParams, fields=VEO_FIELDS,
                      usage_metrics=["video_seconds", "video_seconds_with_audio"]),
        ]

    def estimate_usage(self, model: ModelSpec, params: dict[str, Any]) -> dict[str, float]:
        if params.get("audio"):
            return {"video_seconds_with_audio": params["duration"]}
        return {"video_seconds": params["duration"]}

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {current_app.config['RUNWAY_API_KEY']}",
            "X-Runway-Version": API_VERSION,
        }

    def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        try:
            response = httpx.request(method, f"{BASE_URL}{path}", headers=self._headers(),
                                     timeout=httpx.Timeout(60.0, connect=10.0), **kwargs)
        except httpx.HTTPError as exc:
            raise ProviderError("Runway could not be reached.", code="provider_unavailable",
                                retryable=True) from exc
        if response.status_code >= 400:
            code, retryable = classify_http_status(response.status_code)
            detail = provider_error_text(response)
            # Runway's docs do not list a specific code for an empty credit balance; its own
            # message mentioning credits is taken as that case.
            if detail and "credit" in detail.lower() and response.status_code < 500:
                raise out_of_credit("Runway")
            suffix = f": {detail}" if detail else "."
            raise ProviderError(f"Runway returned an error ({response.status_code}){suffix}", code=code,
                                retryable=retryable)
        return response

    def submit(self, ctx: JobContext) -> ProviderOutcome:
        p = ctx.params
        body: dict[str, Any] = {"model": ctx.model, "ratio": p["ratio"], "duration": p["duration"]}
        if p.get("prompt_text"):
            body["promptText"] = p["prompt_text"]
        if p.get("seed") is not None:
            body["seed"] = p["seed"]
        if ctx.model == "veo3.1_fast":
            body["audio"] = bool(p.get("audio"))
        path = "/v1/text_to_video"
        if p["mode"] == "image_to_video":
            data, mime = ctx.load_asset(uuid.UUID(p["reference_asset_id"]))
            if mime not in ("image/png", "image/jpeg", "image/webp"):
                raise ProviderError("The reference must be a PNG, JPEG or WebP image.",
                                    code="invalid_reference")
            if len(data) > MAX_PROMPT_IMAGE_BYTES:
                raise ProviderError("The reference image must be 5 MB or smaller.",
                                    code="invalid_reference")
            body["promptImage"] = f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"
            path = "/v1/image_to_video"

        task = self._request("POST", path, json=body).json()
        task_id = task.get("id") if isinstance(task, dict) else None
        if not task_id:
            raise ProviderError("Runway's response did not include a task ID.",
                                code="unexpected_provider_response")
        return ProviderOutcome(status="pending", provider_job_id=str(task_id), progress=0)

    def poll(self, ctx: JobContext) -> ProviderOutcome:
        task = self._request("GET", f"/v1/tasks/{ctx.provider_job_id}").json()
        status = task.get("status")
        p = ctx.params
        usage = self.estimate_usage(None, p)  # type: ignore[arg-type]
        if status in ("PENDING", "THROTTLED", "RUNNING"):
            progress = task.get("progress")
            if isinstance(progress, (int, float)):
                progress = int(progress * 100) if progress <= 1 else int(progress)
            return ProviderOutcome(status="pending", provider_job_id=ctx.provider_job_id,
                                   progress=progress if isinstance(progress, int) else None)
        if status == "SUCCEEDED":
            urls = [u for u in (task.get("output") or []) if isinstance(u, str)]
            if not urls:
                raise ProviderError("Runway finished without an output file.", code="empty_result",
                                    usage=usage)
            outputs = [
                ProviderOutput(kind=AssetKind.VIDEO, mime_type="video/mp4",
                               display_name=f"Video {index + 1}" if len(urls) > 1 else "Video",
                               open_stream=_downloader(url), duration_seconds=float(p["duration"]))
                for index, url in enumerate(urls)
            ]
            return ProviderOutcome(status="completed", provider_job_id=ctx.provider_job_id,
                                   progress=100, outputs=outputs, usage=usage,
                                   result={"runway_task_id": ctx.provider_job_id,
                                           # Kept only if Runway's task object reports one (not documented).
                                           "provider_reported": {"cost": task["cost"]}
                                           if task.get("cost") is not None else None})
        if status == "FAILED":
            failure_code = str(task.get("failureCode") or "")
            reported = {k: task[k] for k in ("failureCode", "cost") if task.get(k) is not None} or None
            if failure_code.upper().startswith("SAFETY."):
                # Blocked by Runway's content moderation. Runway's docs say moderated
                # generations cost the same as successful ones (and SAFETY.INPUT.* credits are
                # not refunded), so ASZDA records that cost as its own; the customer is refunded.
                # Runway asks that the code's detail is not shown to users and the task is
                # not retried, hence the generic message and the "content_refused" code.
                raise ProviderError(
                    "Runway's safety system declined this request, so no video was made. Your "
                    "credits were returned. Please change the prompt or image before trying again.",
                    code="content_refused", absorbed_usage=usage,
                    provider_reported={**(reported or {}), "safety_block": True})
            # Other failures: Runway's docs say their credits are refunded, so the user is
            # not charged either.
            raise ProviderError(task.get("failure") or "Runway could not generate this video.",
                                code=f"runway_{(failure_code or 'failed').lower()}"[:64],
                                provider_reported=reported)
        if status == "CANCELLED":
            raise ProviderError("The video generation was cancelled at Runway.", code="provider_cancelled")
        raise ProviderError(f"Unexpected Runway task status: {status!r}", code="unexpected_provider_response")

    def cancel(self, ctx: JobContext) -> bool:
        if not ctx.provider_job_id:
            return False
        self._request("DELETE", f"/v1/tasks/{ctx.provider_job_id}")
        return True


def _downloader(url: str):
    """Return a callable that streams the output file into a temporary file."""

    def open_stream():
        import tempfile

        if not url.startswith("https://"):
            raise ProviderError("Runway returned a non-HTTPS output URL.", code="unexpected_provider_response")
        tmp = tempfile.SpooledTemporaryFile(max_size=16 * 1024 * 1024)
        size = 0
        try:
            with httpx.stream("GET", url, timeout=httpx.Timeout(300.0, connect=15.0),
                              follow_redirects=True) as response:
                if response.status_code != 200:
                    raise ProviderError("The video could not be downloaded from Runway.",
                                        code="output_download_failed", retryable=True)
                for chunk in response.iter_bytes(1024 * 1024):
                    size += len(chunk)
                    if size > MAX_OUTPUT_BYTES:
                        raise ProviderError("The generated video is unexpectedly large.",
                                            code="output_too_large")
                    tmp.write(chunk)
        except httpx.HTTPError as exc:
            raise ProviderError("The video could not be downloaded from Runway.",
                                code="output_download_failed", retryable=True) from exc
        tmp.seek(0)
        return tmp

    return open_stream
