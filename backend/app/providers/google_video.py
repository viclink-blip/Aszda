"""Google: Veo video generation, and image generation with Gemini image models (see
google_image.py), through the official `google-genai` Python SDK.

Two ways to connect (the SDK supports both with the same calls):
- Gemini API: GEMINI_API_KEY (from Google AI Studio).
- Vertex AI ("Gemini Enterprise Agent Platform"): GOOGLE_GENAI_USE_VERTEXAI=true,
  GOOGLE_CLOUD_PROJECT, GOOGLE_CLOUD_LOCATION, and Google Cloud credentials on the server
  (GOOGLE_APPLICATION_CREDENTIALS pointing to a service-account file, or the platform's
  default credentials).

Model IDs are NOT built in: set ASZDA_GOOGLE_VIDEO_MODELS. On 2026-10-22 Google's docs (read
through search summaries) listed the Gemini API Veo 3.1 preview models as shut down that
day, and the GA model veo-3.1-generate-001 only for Vertex AI. Check which models your
account can use with the admin connection test (it looks each model up) before pricing them.

Checked against the SDK source (google-genai 2.32.0) on 2026-10-22:
- start: client.models.generate_videos(model, source=GenerateVideosSource(prompt, image),
  config=GenerateVideosConfig(...)) returns a long-running operation (its `name` is stored);
- poll: client.operations.get(GenerateVideosOperation(name=...)) until `done`; the result
  has generated_videos[].video (uri and/or video_bytes) and rai_media_filtered_count /
  rai_media_filtered_reasons when Google's safety filters removed videos;
- download: video_bytes when returned inline, else client.files.download(file=video)
  (Gemini API only);
- the Gemini API rejects `seed`, `generate_audio` and `fps` (the SDK raises), so they are
  not offered. Veo 3.x adds audio itself.
Duration 4/6/8 s, aspect ratio 16:9 or 9:16, resolution 720p or 1080p (1080p only with
8 s) follow Google's Veo docs as summarised by search on 2026-10-22; re-check them for the
models you enable.

Usage metrics (for credit prices): video_seconds_720p, video_seconds_1080p.
Not implemented: cancelling a running operation, video extension, reference images,
last-frame interpolation and 4k (not confirmed for the Gemini API).
"""

from __future__ import annotations

import uuid
from typing import Any, Literal

from flask import current_app
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models import AssetKind, GenerationKind
from app.providers import google_image
from app.providers.base import (
    JobContext,
    ModelSpec,
    ProviderAdapter,
    ProviderError,
    ProviderOutcome,
    ProviderOutput,
    SettingField,
)

MAX_PROMPT_IMAGE_BYTES = 20 * 1024 * 1024
MAX_OUTPUT_BYTES = 1024 * 1024 * 1024
REQUEST_TIMEOUT_MS = 120_000


class VeoParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["text_to_video", "image_to_video"] = "text_to_video"
    prompt_text: str | None = Field(default=None, max_length=2000)
    negative_prompt: str | None = Field(default=None, max_length=1000)
    reference_asset_id: uuid.UUID | None = None
    aspect_ratio: Literal["16:9", "9:16"] = "16:9"
    duration: Literal[4, 6, 8] = 8
    resolution: Literal["720p", "1080p"] = "720p"
    person_generation: Literal["allow_adult", "dont_allow", "allow_all"] | None = None

    @model_validator(mode="after")
    def check(self):
        if self.mode == "image_to_video" and self.reference_asset_id is None:
            raise ValueError("Image-to-video needs a reference image.")
        if self.mode == "text_to_video":
            self.reference_asset_id = None
            if not (self.prompt_text or "").strip():
                raise ValueError("Text-to-video needs a prompt.")
        if self.resolution == "1080p" and self.duration != 8:
            raise ValueError("1080p videos must be 8 seconds long.")
        if self.person_generation == "allow_all" and self.mode != "text_to_video":
            raise ValueError("'allow_all' people generation is only for text-to-video.")
        return self


FIELDS = [
    SettingField("mode", "Start from", "select", required=True, default="text_to_video",
                 options=[{"value": "text_to_video", "label": "Text prompt"},
                          {"value": "image_to_video", "label": "Reference image + prompt"}]),
    SettingField("prompt_text", "Prompt", "textarea", max_length=2000,
                 help="Describe the subject, action, camera, style and sound."),
    SettingField("negative_prompt", "Avoid (optional)", "textarea", max_length=1000,
                 help="Things the video should not contain."),
    SettingField("reference_asset_id", "Reference image", "asset", asset_kind="image",
                 help="Used as the first frame.", show_when={"mode": ["image_to_video"]}),
    SettingField("aspect_ratio", "Aspect ratio", "select", default="16:9",
                 options=[{"value": "16:9", "label": "Landscape 16:9"}, {"value": "9:16", "label": "Portrait 9:16"}]),
    SettingField("duration", "Length (seconds)", "select", default="8",
                 options=[{"value": "4", "label": "4 seconds"}, {"value": "6", "label": "6 seconds"},
                          {"value": "8", "label": "8 seconds"}]),
    SettingField("resolution", "Resolution", "select", default="720p",
                 options=[{"value": "720p", "label": "720p"}, {"value": "1080p", "label": "1080p (8 seconds only)"}]),
    SettingField("person_generation", "People", "select",
                 options=[{"value": "allow_adult", "label": "Adults only"},
                          {"value": "dont_allow", "label": "No people"},
                          {"value": "allow_all", "label": "Allow all (text-to-video only)"}],
                 help="Some regions allow only 'Adults only'. Leave empty for Google's default."),
]


def _errors():
    from google.genai import errors

    return errors


class GoogleVideoAdapter(ProviderAdapter):
    name = "google"
    label = "Google"
    credential_env = "GEMINI_API_KEY"
    supports_cancel = False
    default_model_settings = {GenerationKind.VIDEO: "GOOGLE_VIDEO_MODEL",
                              GenerationKind.IMAGE: "GOOGLE_IMAGE_MODEL"}
    connection_test = ("Looks up each configured Veo and image model (models.get). Nothing is generated; Google "
                       "does not document a charge for model lookups.")

    # ---- Configuration -------------------------------------------------------------------

    def _vertex(self) -> bool:
        return bool(current_app.config.get("GOOGLE_USE_VERTEXAI"))

    def missing_settings(self) -> list[str]:
        cfg = current_app.config
        missing = []
        if self._vertex():
            missing += [n for n, k in (("GOOGLE_CLOUD_PROJECT", "GOOGLE_CLOUD_PROJECT"),
                                       ("GOOGLE_CLOUD_LOCATION", "GOOGLE_CLOUD_LOCATION")) if not cfg.get(k)]
        elif not cfg.get("GEMINI_API_KEY"):
            missing.append("GEMINI_API_KEY")
        if not cfg.get("GOOGLE_VIDEO_MODELS") and not cfg.get("GOOGLE_IMAGE_MODELS"):
            missing.append("ASZDA_GOOGLE_VIDEO_MODELS or ASZDA_GOOGLE_IMAGE_MODELS")
        return missing

    def is_configured(self) -> bool:
        return not self.missing_settings()

    def model_specs(self) -> list[ModelSpec]:
        return [
            ModelSpec(id=model_id, label=f"Google {model_id}", kind=GenerationKind.VIDEO,
                      description="Video with sound from a text prompt or a first-frame image, 4–8 seconds.",
                      params_model=VeoParams, fields=FIELDS,
                      usage_metrics=["video_seconds_720p", "video_seconds_1080p"])
            for model_id in current_app.config.get("GOOGLE_VIDEO_MODELS", [])
        ] + google_image.image_specs()

    def estimate_usage(self, model: ModelSpec, params: dict[str, Any]) -> dict[str, float]:
        if model is not None and model.kind == GenerationKind.IMAGE:
            return google_image.estimate_usage(params)
        return {f"video_seconds_{params['resolution']}": params["duration"]}

    def _client(self):
        from google import genai
        from google.genai import types

        options = types.HttpOptions(timeout=REQUEST_TIMEOUT_MS)
        cfg = current_app.config
        if self._vertex():
            return genai.Client(vertexai=True, project=cfg["GOOGLE_CLOUD_PROJECT"],
                                location=cfg["GOOGLE_CLOUD_LOCATION"], http_options=options)
        return genai.Client(api_key=cfg["GEMINI_API_KEY"], http_options=options)

    # ---- Errors ----------------------------------------------------------------------------

    def _translate(self, exc: Exception) -> ProviderError:
        errors = _errors()
        if isinstance(exc, errors.ClientError):
            code = getattr(exc, "code", None)
            if code in (401, 403):
                return ProviderError("Google rejected the credential.", code="provider_auth_failed")
            if code == 404:
                return ProviderError("This Google model is not available to this account.", code="model_unavailable")
            if code == 429:
                return ProviderError("Google's rate limit or quota was reached.", code="provider_rate_limited",
                                     retryable=True)
            return ProviderError(f"Google rejected the request ({code}).", code="provider_rejected_request")
        if isinstance(exc, errors.ServerError):
            return ProviderError("Google is unavailable right now.", code="provider_unavailable", retryable=True)
        return ProviderError("Google could not be reached.", code="provider_unavailable", retryable=True)

    def _call(self, fn, *args, **kwargs):
        import httpx

        errors = _errors()
        try:
            return fn(*args, **kwargs)
        except (errors.APIError, httpx.HTTPError, TimeoutError, ConnectionError) as exc:
            raise self._translate(exc) from exc

    # ---- Generation ------------------------------------------------------------------------

    def submit(self, ctx: JobContext) -> ProviderOutcome:
        from google.genai import types

        spec = self.get_model(ctx.model)
        if spec is not None and spec.kind == GenerationKind.IMAGE:
            return google_image.submit(ctx, self._client(), self._call)
        p = ctx.params
        image = None
        if p["mode"] == "image_to_video":
            data, mime = ctx.load_asset(uuid.UUID(p["reference_asset_id"]))
            if mime not in ("image/png", "image/jpeg", "image/webp"):
                raise ProviderError("The reference must be a PNG, JPEG or WebP image.", code="invalid_reference")
            if len(data) > MAX_PROMPT_IMAGE_BYTES:
                raise ProviderError("The reference image is too large.", code="invalid_reference")
            image = types.Image(image_bytes=data, mime_type=mime)
        config = types.GenerateVideosConfig(
            number_of_videos=1, duration_seconds=p["duration"], aspect_ratio=p["aspect_ratio"],
            resolution=p["resolution"], negative_prompt=p.get("negative_prompt") or None,
            person_generation=p.get("person_generation") or None)
        # Keep the client referenced while it is used: google-genai closes its HTTP connection
        # when the Client object is garbage-collected.
        client = self._client()
        operation = self._call(
            client.models.generate_videos, model=ctx.model,
            source=types.GenerateVideosSource(prompt=p.get("prompt_text") or None, image=image), config=config)
        name = getattr(operation, "name", None)
        if not name:
            raise ProviderError("Google's response did not include an operation name.",
                                code="unexpected_provider_response")
        return ProviderOutcome(status="pending", provider_job_id=str(name), progress=0)

    def poll(self, ctx: JobContext) -> ProviderOutcome:
        from google.genai import types

        client = self._client()
        operation = self._call(client.operations.get, types.GenerateVideosOperation(name=ctx.provider_job_id))
        if not operation.done:
            return ProviderOutcome(status="pending", provider_job_id=ctx.provider_job_id)
        if operation.error:
            message = str((operation.error or {}).get("message") or "Google could not generate this video.")
            raise ProviderError(message[:500], code="provider_failed",
                                provider_reported={"error": operation.error})
        result = operation.response or operation.result
        videos = [v.video for v in (getattr(result, "generated_videos", None) or []) if v and v.video]
        filtered = getattr(result, "rai_media_filtered_count", None)
        if not videos:
            if filtered:
                # Removed by Google's safety filters. Google does not document charging for this;
                # the customer is refunded and no provider cost is assumed.
                raise ProviderError(
                    "Google's safety system declined this request, so no video was made. Your credits "
                    "were returned. Please change the prompt or image before trying again.",
                    code="content_refused",
                    provider_reported={"rai_media_filtered_count": filtered,
                                       "rai_media_filtered_reasons": getattr(result, "rai_media_filtered_reasons",
                                                                             None)})
            raise ProviderError("Google finished without a video.", code="empty_result")
        video = videos[0]
        data = video.video_bytes
        if not data:
            if self._vertex():
                raise ProviderError("Google returned only a storage link that ASZDA cannot download.",
                                    code="unexpected_provider_response")
            data = self._call(client.files.download, file=video)
        if not data or len(data) > MAX_OUTPUT_BYTES:
            raise ProviderError("Google returned an unexpected video.", code="unexpected_provider_response")
        p = ctx.params
        return ProviderOutcome(
            status="completed", provider_job_id=ctx.provider_job_id, progress=100,
            outputs=[ProviderOutput(kind=AssetKind.VIDEO, mime_type=video.mime_type or "video/mp4",
                                    display_name="Video", data=data, duration_seconds=float(p["duration"]))],
            usage=self.estimate_usage(None, p),  # type: ignore[arg-type]
            result={"google_operation": ctx.provider_job_id, "rai_media_filtered_count": filtered or 0})

    def params_for_brief(self, model: ModelSpec, brief: dict[str, Any]) -> dict[str, Any]:
        if model.kind == GenerationKind.IMAGE:
            return google_image.params_for_brief(brief)
        prompt = " ".join(x for x in (brief.get("prompt"), brief.get("style")) if x)[:2000]
        seconds = int(brief.get("duration_seconds") or 8)
        params: dict[str, Any] = {
            "prompt_text": prompt, "aspect_ratio": "9:16" if brief.get("orientation") == "portrait" else "16:9",
            "duration": min((4, 6, 8), key=lambda d: abs(d - seconds)), "resolution": "720p"}
        if brief.get("reference_asset_id"):
            params.update(mode="image_to_video", reference_asset_id=str(brief["reference_asset_id"]))
        else:
            params["mode"] = "text_to_video"
        return params

    # ---- Connection test -----------------------------------------------------------------

    def list_media_models(self) -> list[str]:
        """IDs of the image and Veo models this credential can see (models.list; nothing is
        generated). Used to choose ASZDA_GOOGLE_IMAGE_MODELS / ASZDA_GOOGLE_VIDEO_MODELS."""
        found = []
        client = self._client()  # kept referenced (see submit); the pager uses it for every page
        for model in self._call(client.models.list):
            model_id = (getattr(model, "name", None) or "").rsplit("/", 1)[-1]
            if "image" in model_id or "veo" in model_id:
                found.append(model_id)
        return sorted(set(found))

    def test_connection(self) -> str:
        client = self._client()
        found = []
        for spec in self.model_specs():
            model = self._call(client.models.get, model=spec.id)
            found.append(getattr(model, "name", None) or spec.id)
        mode = "Vertex AI" if self._vertex() else "Gemini API"
        return f"{mode} credential accepted; models available: " + ", ".join(found)
