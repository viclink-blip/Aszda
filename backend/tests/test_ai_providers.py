"""Provider integration layer: configuration and readiness, adapter request/response handling
(all provider calls mocked; nothing reaches a real API), orchestrator routing and fallback,
connection tests, the AI Film Director, cost logging and access control."""

import base64
import json
import types as pytypes
import uuid

import httpx
import pytest

from app.extensions import db
from app.models import Asset, GenerationJob, ProviderCost, Scene
from app.providers.anthropic_text import AnthropicTextAdapter
from app.providers.base import JobContext, ProviderError
from app.providers.google_video import GoogleVideoAdapter
from app.providers.openai_speech import OpenAIAdapter
from app.providers.runway_video import RunwayVideoAdapter
from app.services import orchestrator, pricing
from tests.conftest import PNG
from tests.fakes import MP4

SECRET_KEYS = {"ANTHROPIC_API_KEY": "sk-ant-test-secret-111", "OPENAI_API_KEY": "sk-openai-test-secret-222",
               "RUNWAY_API_KEY": "key_runway_test_secret_333", "GEMINI_API_KEY": "gemini-test-secret-444"}


def idem() -> dict:
    return {"Idempotency-Key": f"test-{uuid.uuid4()}"}


@pytest.fixture()
def app_ctx(app):
    with app.app_context():
        yield app


@pytest.fixture()
def cfg(app, monkeypatch):
    """Set config values for one test (restored afterwards)."""
    def setter(**values):
        for key, value in values.items():
            monkeypatch.setitem(app.config, key, value)
    return setter


def price(**rates):
    return pricing.ModelPrice(credits_per_1000=rates, minimum_credits=1)


def add_prices(prices: dict):
    pricing.set_override({**(pricing._overrides or {}), **prices})


def ctx(model, params, provider_job_id=None, load_asset=None):
    return JobContext(job_id=uuid.uuid4(), model=model, params=params, provider_job_id=provider_job_id,
                      load_asset=load_asset or (lambda _id: (PNG, "image/png")))


# ---- Missing credentials and configuration ---------------------------------------------------

def test_missing_credentials_do_not_crash_and_make_providers_unavailable(app, make_user):
    user = make_user(credits=100)
    providers = {p["name"]: p for p in user.get("/api/providers").get_json()["providers"]}
    for name in ("anthropic", "openai", "runway", "google"):
        assert providers[name]["configured"] is False
        assert all(m["unavailable_reason"] == "provider_not_configured" for m in providers[name]["models"])
    assert providers["openai"]["capabilities"] == ["speech", "image"]
    assert providers["runway"]["capabilities"] == ["video"]
    # Paid generation is refused for an unconfigured provider, with nothing reserved.
    response = user.post("/api/generation-jobs", headers=idem(), json={
        "provider": "openai", "kind": "image", "params": {"prompt": "A red fox"}})
    assert response.status_code == 503 and response.get_json()["error"]["code"] == "provider_not_configured"
    assert user.get("/api/me/credits").get_json()["account"]["balance"] == 100


def test_health_lists_missing_setting_names_and_never_secret_values(app, make_user, cfg):
    admin = make_user(admin=True)
    body = admin.get("/api/admin/providers/health").get_json()
    health = {p["name"]: p for p in body["providers"]}
    assert health["anthropic"]["missing_settings"] == ["ANTHROPIC_API_KEY"]
    assert health["google"]["missing_settings"] == ["GEMINI_API_KEY", "ASZDA_GOOGLE_VIDEO_MODELS"]
    assert health["openai"]["credentials_configured"] is False
    assert health["runway"]["connection_test"]["available"] is True
    assert health["runway"]["connection_test"]["may_charge"] is False
    # With keys set, the values never appear in any provider listing.
    cfg(**SECRET_KEYS, GOOGLE_VIDEO_MODELS=["veo-test"])
    dumped = json.dumps(admin.get("/api/admin/providers/health").get_json()) + \
        json.dumps(admin.get("/api/admin/providers").get_json()) + \
        json.dumps(admin.get("/api/providers").get_json())
    for secret in SECRET_KEYS.values():
        assert secret not in dumped
    health = {p["name"]: p for p in admin.get("/api/admin/providers/health").get_json()["providers"]}
    assert health["google"]["settings_complete"] is True and health["openai"]["settings_complete"] is True


def test_health_endpoints_are_admin_only(app, make_user):
    user = make_user()
    assert user.get("/api/admin/providers/health").status_code == 403
    assert user.post("/api/admin/providers/anthropic/test").status_code == 403
    assert user.get("/api/admin/provider-costs").status_code == 403


def test_google_configuration_validation(app_ctx, cfg):
    adapter = GoogleVideoAdapter()
    cfg(GOOGLE_USE_VERTEXAI=True, GOOGLE_VIDEO_MODELS=["veo-3.1-generate-001"])
    assert adapter.missing_settings() == ["GOOGLE_CLOUD_PROJECT", "GOOGLE_CLOUD_LOCATION"]
    cfg(GOOGLE_CLOUD_PROJECT="my-project", GOOGLE_CLOUD_LOCATION="us-central1")
    assert adapter.is_configured()
    cfg(GOOGLE_VIDEO_MODELS=[])
    assert adapter.missing_settings() == ["ASZDA_GOOGLE_VIDEO_MODELS"] and adapter.model_specs() == []


def test_disabled_provider_is_unavailable_even_with_a_key(app, make_user, cfg):
    cfg(OPENAI_API_KEY="k", DISABLED_PROVIDERS=["openai"])
    add_prices({"openai:gpt-image-2.5-sunburst": price(images_medium=10_000)})
    user = make_user(credits=100)
    response = user.post("/api/generation-jobs", headers=idem(), json={
        "provider": "openai", "kind": "image", "params": {"prompt": "A red fox"}})
    assert response.status_code == 503 and response.get_json()["error"]["code"] == "provider_disabled"


# ---- OpenAI images -----------------------------------------------------------------------------

def _image_response(status=200, body=None):
    return lambda *a, **k: httpx.Response(status, json=body if body is not None else {
        "created": 1, "output_format": "png", "quality": "medium",
        "data": [{"b64_json": base64.b64encode(PNG).decode()}],
        "usage": {"input_tokens": 20, "output_tokens": 1000, "total_tokens": 1020,
                  "input_tokens_details": {"image_tokens": 0, "text_tokens": 20}}})


def test_openai_image_request_and_response(app_ctx, cfg, monkeypatch):
    cfg(OPENAI_API_KEY="k")
    adapter = OpenAIAdapter()
    spec = adapter.get_model("gpt-image-2.5-sunburst")
    params = adapter.validate(spec, {"prompt": "A red fox", "size": "1536x1024", "quality": "high"})
    assert adapter.estimate_usage(spec, params) == {"images_high": 1}
    sent = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        sent.update(url=url, body=json, headers=headers)
        return _image_response()()
    monkeypatch.setattr(httpx, "post", fake_post)
    outcome = adapter.submit(ctx("gpt-image-2.5-sunburst", params))
    assert sent["url"] == "https://api.openai.com/v1/images/generations"
    assert sent["body"] == {"model": "gpt-image-2.5-sunburst", "prompt": "A red fox", "n": 1, "size": "1536x1024",
                            "quality": "high", "output_format": "png", "background": "auto"}
    assert outcome.status == "completed" and outcome.outputs[0].data == PNG
    assert (outcome.outputs[0].width, outcome.outputs[0].height) == (1536, 1024)
    assert outcome.result["provider_reported"]["usage"]["output_tokens"] == 1000
    with pytest.raises(Exception):
        adapter.validate(spec, {"prompt": "x", "background": "transparent", "output_format": "jpeg"})


@pytest.mark.parametrize("status,body,code,retryable", [
    (400, {"error": {"code": "moderation_blocked", "message": "blocked"}}, "content_refused", False),
    (429, {"error": {"message": "slow down"}}, "provider_rate_limited", True),
    (500, {"error": {}}, "provider_unavailable", True),
    (404, {"error": {"message": "no such model"}}, "model_unavailable", False),
    (401, {"error": {}}, "provider_auth_failed", False),
    (200, {"data": []}, "empty_result", False),
    (200, {"data": [{"b64_json": "!!!not-base64"}]}, "unexpected_provider_response", False),
])
def test_openai_image_errors(app_ctx, cfg, monkeypatch, status, body, code, retryable):
    cfg(OPENAI_API_KEY="k")
    monkeypatch.setattr(httpx, "post", _image_response(status, body))
    with pytest.raises(ProviderError) as err:
        OpenAIAdapter().submit(ctx("gpt-image-2", {"prompt": "x", "size": "1024x1024", "quality": "low",
                                                    "output_format": "png", "background": "auto"}))
    assert err.value.code == code and err.value.retryable is retryable


def test_openai_timeout_is_retryable(app_ctx, cfg, monkeypatch):
    cfg(OPENAI_API_KEY="k")

    def boom(*a, **k):
        raise httpx.ReadTimeout("slow")
    monkeypatch.setattr(httpx, "post", boom)
    with pytest.raises(ProviderError) as err:
        OpenAIAdapter().submit(ctx("gpt-image-2", {"prompt": "x", "size": "1024x1024", "quality": "low",
                                                    "output_format": "png", "background": "auto"}))
    assert err.value.retryable and err.value.code == "provider_unavailable"


def test_openai_speech_still_works_through_merged_adapter(app_ctx, cfg, monkeypatch):
    cfg(OPENAI_API_KEY="k")
    adapter = OpenAIAdapter()
    spec = adapter.get_model("gpt-4o-mini-tts")
    params = adapter.validate(spec, {"text": "Hello there"})
    assert params["voice"] == "marin"
    monkeypatch.setattr(httpx, "post", lambda *a, **k: httpx.Response(200, content=b"ID3audio"))
    outcome = adapter.submit(ctx("gpt-4o-mini-tts", params))
    assert outcome.outputs[0].mime_type == "audio/mpeg" and outcome.usage == {"characters": 11}
    legacy = adapter.get_model("tts-1")
    assert adapter.validate(legacy, {"text": "Hi"})["voice"] == "alloy"
    with pytest.raises(Exception):
        adapter.validate(legacy, {"text": "Hi", "voice": "marin"})  # tts-1 has fewer voices


# ---- Google Veo (SDK mocked) ------------------------------------------------------------------------

class FakeGenai:
    """Stands in for google.genai.Client: records calls, returns scripted operations."""

    def __init__(self):
        self.calls = []
        self.operations_queue = []
        self.models = pytypes.SimpleNamespace(generate_videos=self._generate, get=self._get_model)
        self.operations = pytypes.SimpleNamespace(get=self._get_operation)
        self.files = pytypes.SimpleNamespace(download=self._download)

    def _generate(self, **kwargs):
        self.calls.append(("generate", kwargs))
        return pytypes.SimpleNamespace(name="models/veo/operations/op-123", done=False)

    def _get_operation(self, op):
        self.calls.append(("get", op.name))
        return self.operations_queue.pop(0)

    def _download(self, file):
        self.calls.append(("download", file.uri))
        return MP4

    def _get_model(self, model):
        self.calls.append(("model", model))
        return pytypes.SimpleNamespace(name=f"models/{model}")


def done_op(videos=None, filtered=None, error=None):
    result = pytypes.SimpleNamespace(generated_videos=videos or [], rai_media_filtered_count=filtered,
                                     rai_media_filtered_reasons=["reason"] if filtered else None)
    return pytypes.SimpleNamespace(done=True, error=error, response=result, result=result)


@pytest.fixture()
def google(app_ctx, cfg, monkeypatch):
    cfg(GEMINI_API_KEY="g", GOOGLE_VIDEO_MODELS=["veo-test-model"])
    fake = FakeGenai()
    monkeypatch.setattr(GoogleVideoAdapter, "_client", lambda self: fake)
    return fake


def test_google_video_submit_poll_and_download(google):
    adapter = GoogleVideoAdapter()
    spec = adapter.get_model("veo-test-model")
    params = adapter.validate(spec, {"mode": "image_to_video", "prompt_text": "A fox runs",
                                     "reference_asset_id": str(uuid.uuid4()), "duration": 8, "resolution": "1080p"})
    assert adapter.estimate_usage(spec, params) == {"video_seconds_1080p": 8}
    pending = adapter.submit(ctx("veo-test-model", params))
    assert pending.status == "pending" and pending.provider_job_id == "models/veo/operations/op-123"
    _, sent = google.calls[0]
    assert sent["model"] == "veo-test-model" and sent["source"].prompt == "A fox runs"
    assert sent["source"].image.image_bytes == PNG and sent["source"].image.mime_type == "image/png"
    assert (sent["config"].duration_seconds, sent["config"].resolution, sent["config"].aspect_ratio,
            sent["config"].number_of_videos) == (8, "1080p", "16:9", 1)

    google.operations_queue = [pytypes.SimpleNamespace(done=False, error=None),
                               done_op(videos=[pytypes.SimpleNamespace(video=pytypes.SimpleNamespace(
                                   uri="https://generativelanguage.googleapis.com/v1beta/files/x",
                                   video_bytes=None, mime_type="video/mp4"))])]
    assert adapter.poll(ctx("veo-test-model", params, provider_job_id=pending.provider_job_id)).status == "pending"
    finished = adapter.poll(ctx("veo-test-model", params, provider_job_id=pending.provider_job_id))
    assert finished.status == "completed" and finished.outputs[0].data == MP4
    assert finished.usage == {"video_seconds_1080p": 8}
    assert ("download", "https://generativelanguage.googleapis.com/v1beta/files/x") in google.calls


def test_google_video_validation(google):
    adapter = GoogleVideoAdapter()
    spec = adapter.get_model("veo-test-model")
    with pytest.raises(Exception):
        adapter.validate(spec, {"prompt_text": "x", "duration": 4, "resolution": "1080p"})  # 1080p needs 8 s
    with pytest.raises(Exception):
        adapter.validate(spec, {"mode": "text_to_video"})  # no prompt
    with pytest.raises(Exception):
        adapter.validate(spec, {"prompt_text": "x", "seed": 3})  # not supported on the Gemini API


def test_google_safety_filter_and_failures(google):
    adapter = GoogleVideoAdapter()
    params = adapter.validate(adapter.get_model("veo-test-model"), {"prompt_text": "x"})
    google.operations_queue = [done_op(filtered=1)]
    with pytest.raises(ProviderError) as err:
        adapter.poll(ctx("veo-test-model", params, provider_job_id="op"))
    # Refunded; Google does not document charging for filtered videos, so no cost is assumed.
    assert err.value.code == "content_refused" and err.value.absorbed_usage == {}
    assert err.value.provider_reported["rai_media_filtered_count"] == 1
    google.operations_queue = [done_op(error={"code": 13, "message": "internal"})]
    with pytest.raises(ProviderError) as err:
        adapter.poll(ctx("veo-test-model", params, provider_job_id="op"))
    assert err.value.code == "provider_failed"
    google.operations_queue = [done_op()]
    with pytest.raises(ProviderError) as err:
        adapter.poll(ctx("veo-test-model", params, provider_job_id="op"))
    assert err.value.code == "empty_result"


def test_google_api_errors_are_translated(google, monkeypatch):
    from google.genai import errors

    adapter = GoogleVideoAdapter()
    params = adapter.validate(adapter.get_model("veo-test-model"), {"prompt_text": "x"})
    for status, code, retryable in ((429, "provider_rate_limited", True), (404, "model_unavailable", False),
                                    (403, "provider_auth_failed", False)):
        def raise_it(**kwargs):
            raise errors.ClientError(status, {"error": {"code": status, "message": "m", "status": "X"}})
        monkeypatch.setattr(google.models, "generate_videos", raise_it)
        with pytest.raises(ProviderError) as err:
            adapter.submit(ctx("veo-test-model", params))
        assert (err.value.code, err.value.retryable) == (code, retryable)

    def server_error(**kwargs):
        raise errors.ServerError(503, {"error": {"code": 503, "message": "m", "status": "UNAVAILABLE"}})
    monkeypatch.setattr(google.models, "generate_videos", server_error)
    with pytest.raises(ProviderError) as err:
        adapter.submit(ctx("veo-test-model", params))
    assert err.value.retryable


def test_google_vertex_inline_bytes(google, cfg):
    cfg(GOOGLE_USE_VERTEXAI=True, GOOGLE_CLOUD_PROJECT="p", GOOGLE_CLOUD_LOCATION="us-central1")
    adapter = GoogleVideoAdapter()
    params = adapter.validate(adapter.get_model("veo-test-model"), {"prompt_text": "x", "duration": 4})
    google.operations_queue = [done_op(videos=[pytypes.SimpleNamespace(video=pytypes.SimpleNamespace(
        uri=None, video_bytes=MP4, mime_type="video/mp4"))])]
    outcome = adapter.poll(ctx("veo-test-model", params, provider_job_id="op"))
    assert outcome.outputs[0].data == MP4 and not [c for c in google.calls if c[0] == "download"]


# ---- Anthropic director plan (SDK mocked) ---------------------------------------------------------

PLAN = {"title": "The Fox", "logline": "A fox sells shoes.", "style": "Warm watercolour",
        "characters": [{"name": "Fox", "description": "Small red fox with a satchel", "voice": "bright"}],
        "scenes": [{"title": "Market", "description": "Fox opens a shoe stall.", "shot": "Wide, slow push-in",
                    "dialogue": "Shoes! Fresh shoes!", "narration": "Every morning, Fox opened the stall.",
                    "duration_seconds": 30, "image_prompt": "A red fox at a market stall, watercolour",
                    "video_prompt": "The fox arranges shoes, birds chirp", "characters": ["Fox"]},
                   {"title": "Night", "description": "Fox counts coins.", "shot": "Close-up", "dialogue": "",
                    "narration": "", "duration_seconds": 1, "image_prompt": "Fox counting coins by lamplight",
                    "video_prompt": "Coins clink", "characters": ["Fox", "Nobody"]}]}


class FakeAnthropic:
    def __init__(self, text: str, stop_reason="end_turn"):
        self.sent = None
        usage = pytypes.SimpleNamespace(input_tokens=900, output_tokens=2500)
        self.response = pytypes.SimpleNamespace(
            usage=usage, stop_reason=stop_reason, model="claude-opus-5-5",
            content=[pytypes.SimpleNamespace(type="text", text=text)])
        self.beta = pytypes.SimpleNamespace(messages=pytypes.SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.sent = kwargs
        return self.response


def test_director_plan_uses_structured_output(app_ctx, cfg, monkeypatch):
    cfg(ANTHROPIC_API_KEY="k")
    fake = FakeAnthropic(json.dumps(PLAN))
    monkeypatch.setattr(AnthropicTextAdapter, "_client", lambda self: fake)
    adapter = AnthropicTextAdapter()
    spec = adapter.get_model("claude-opus-5-5")
    params = adapter.validate(spec, {"task": "director_plan", "prompt": "A fox who sells shoes"})
    outcome = adapter.submit(ctx("claude-opus-5-5", params))
    assert fake.sent["output_config"]["format"]["type"] == "json_schema"
    assert fake.sent["output_config"]["effort"] == "medium" and fake.sent["fallbacks"] == "default"
    plan = outcome.result["plan"]
    assert [s["duration_seconds"] for s in plan["scenes"]] == [10, 4]  # clamped to 4-10 s
    assert outcome.outputs[0].mime_type == "text/markdown" and b"# The Fox" in outcome.outputs[0].data

    cut = FakeAnthropic('{"title": "The Fo', stop_reason="max_tokens")
    monkeypatch.setattr(AnthropicTextAdapter, "_client", lambda self: cut)
    with pytest.raises(ProviderError) as err:
        adapter.submit(ctx("claude-opus-5-5", params))
    assert err.value.code == "incomplete_plan" and err.value.usage == {"input_tokens": 900, "output_tokens": 2500}


# ---- Connection tests ------------------------------------------------------------------------------

def test_connection_tests_store_success_and_errors(app, make_user, cfg, monkeypatch):
    admin = make_user(admin=True)
    response = admin.post("/api/admin/providers/runway/test")
    assert response.status_code == 409 and response.get_json()["error"]["code"] == "provider_not_configured"

    cfg(RUNWAY_API_KEY="r")
    monkeypatch.setattr(httpx, "request", lambda method, url, **k: httpx.Response(
        200, json={"creditBalance": 1234, "tier": {}, "usage": {}}) if url.endswith("/v1/organization")
        else httpx.Response(500))
    result = admin.post("/api/admin/providers/runway/test").get_json()["provider"]
    assert result["last_test"]["ok"] is True and "1234" in result["last_test"]["result"]

    monkeypatch.setattr(httpx, "request", lambda *a, **k: httpx.Response(401))
    result = admin.post("/api/admin/providers/runway/test").get_json()["provider"]
    assert result["last_test"]["ok"] is False and result["last_test"]["last_success_at"] is not None
    assert "401" in result["last_test"]["last_error"]

    cfg(OPENAI_API_KEY="o")
    monkeypatch.setattr(httpx, "get", lambda url, **k: httpx.Response(404))
    result = admin.post("/api/admin/providers/openai/test").get_json()["provider"]
    assert result["last_test"]["ok"] is False and "not available" in result["last_test"]["last_error"]

    cfg(ANTHROPIC_API_KEY="a")
    models = pytypes.SimpleNamespace(retrieve=lambda model_id: pytypes.SimpleNamespace(id=model_id))
    client = pytypes.SimpleNamespace(models=models, with_options=lambda **kw: client)
    monkeypatch.setattr(AnthropicTextAdapter, "_client", lambda self: client)
    result = admin.post("/api/admin/providers/anthropic/test").get_json()["provider"]
    assert result["last_test"]["ok"] is True and "claude-opus-5-5" in result["last_test"]["result"]


def test_connection_test_that_may_charge_needs_confirmation(app, make_user, cfg, monkeypatch):
    admin = make_user(admin=True)
    cfg(RUNWAY_API_KEY="r")
    monkeypatch.setattr(RunwayVideoAdapter, "connection_test_may_charge", True)
    monkeypatch.setattr(httpx, "request", lambda *a, **k: httpx.Response(200, json={"creditBalance": 1}))
    response = admin.post("/api/admin/providers/runway/test")
    assert response.status_code == 409 and response.get_json()["error"]["code"] == "charge_confirmation_required"
    assert admin.post("/api/admin/providers/runway/test", json={"confirm_charge": True}).status_code == 200


# ---- Routing ----------------------------------------------------------------------------------------

def test_routing_uses_configured_provider_then_fallback(app, make_user, cfg):
    cfg(AI_VIDEO_PROVIDER="runway", AI_VIDEO_FALLBACKS=["fake-video"])
    user = make_user(credits=200)
    # Runway has no key: the request falls back to the next provider that offers video.
    response = user.post("/api/generation-jobs", headers=idem(), json={
        "kind": "video", "params": {"prompt_text": "A fox runs", "duration": 5}})
    assert response.status_code == 201, response.get_json()
    job = response.get_json()["job"]
    assert (job["provider"], job["model"]) == ("fake-video", "fake-motion")
    with app.app_context():
        routing = db.session.get(GenerationJob, uuid.UUID(job["id"])).usage["routing"]
        assert routing["fallback_used"] is True
        assert routing["skipped"] == [{"provider": "runway", "reason": "provider_not_configured"}]
        asset = db.session.query(Asset).filter_by(generation_job_id=uuid.UUID(job["id"])).one()
        assert (asset.provider, asset.model) == ("fake-video", "fake-motion")
    capabilities = {c["kind"]: c for c in user.get("/api/ai/capabilities").get_json()["capabilities"]}
    assert capabilities["video"]["ready"] == {"provider": "fake-video", "model": "fake-motion", "fallback_used": True}
    assert capabilities["image"]["ready"] is None
    assert capabilities["image"]["problem"]["code"] == "no_provider_available"


def test_explicit_provider_is_never_replaced(app, make_user, cfg):
    cfg(AI_VIDEO_PROVIDER="runway", AI_VIDEO_FALLBACKS=["fake-video"])
    user = make_user(credits=200)
    response = user.post("/api/generation-jobs", headers=idem(), json={
        "provider": "runway", "kind": "video", "params": {"prompt_text": "x", "ratio": "1280:720"}})
    assert response.status_code == 503 and response.get_json()["error"]["code"] == "provider_not_configured"


def test_routing_errors(app, make_user, cfg):
    user = make_user(credits=200)
    cases = [
        ({"provider": "fake-text", "kind": "video", "params": {}}, 422, "unsupported_capability"),
        ({"provider": "fake-video", "model": "nope", "kind": "video", "params": {}}, 422, "unsupported_model"),
        ({"model": "fake-motion", "kind": "video", "params": {}}, 422, "provider_required"),
        ({"provider": "nobody", "kind": "video", "params": {}}, 404, "unknown_provider"),
        ({"kind": "animation", "params": {}}, 422, "provider_required"),
    ]
    for body, status, code in cases:
        response = user.post("/api/generation-jobs", headers=idem(), json=body)
        assert (response.status_code, response.get_json()["error"]["code"]) == (status, code), body
    cfg(AI_VIDEO_PROVIDER="runway", AI_VIDEO_FALLBACKS=["google", "fake-text"])
    response = user.post("/api/generation-jobs", headers=idem(), json={"kind": "video", "params": {}})
    assert response.status_code == 503
    tried = response.get_json()["error"]["details"]["tried"]
    assert [(t["provider"], t["reason"]) for t in tried] == [
        ("runway", "provider_not_configured"), ("google", "provider_not_configured"),
        ("fake-text", "unsupported_capability")]


def test_unpriced_model_cannot_be_used(app, make_user, cfg):
    cfg(OPENAI_API_KEY="k")
    user = make_user(credits=200)
    response = user.post("/api/generation-jobs", headers=idem(), json={
        "provider": "openai", "kind": "image", "params": {"prompt": "x"}})
    assert response.status_code == 409 and response.get_json()["error"]["code"] == "pricing_not_configured"


def test_orchestrator_unit(app_ctx, cfg):
    cfg(AI_TEXT_PROVIDER="fake-text", AI_TEXT_FALLBACKS=[])
    chosen = orchestrator.route(orchestrator.GenerationKind.TEXT)
    assert (chosen.adapter.name, chosen.spec.id, chosen.fallback_used) == ("fake-text", "fake-writer", False)


# ---- Paid generation through real adapters, with credits and cost logging -----------------------------

def test_image_job_reserves_charges_and_logs_cost(app, make_user, cfg, monkeypatch):
    cfg(OPENAI_API_KEY="k")
    add_prices({"openai:gpt-image-2.5-sunburst": pricing.ModelPrice(
        credits_per_1000={"images_low": 3000, "images_medium": 8000, "images_high": 25000}, minimum_credits=1,
        provider_usd_per_1000={"images_medium": 40})})
    monkeypatch.setattr(httpx, "post", _image_response())
    user = make_user(credits=100)
    pid = user.post("/api/projects", json={"title": "P"}).get_json()["project"]["id"]
    response = user.post("/api/generation-jobs", headers=idem(), json={
        "kind": "image", "project_id": pid, "params": {"prompt": "A red fox"}})  # routed to openai
    assert response.status_code == 201, response.get_json()
    job = user.get(f"/api/generation-jobs/{response.get_json()['job']['id']}").get_json()["job"]
    assert job["status"] == "completed" and job["credits_charged"] == 8
    assert user.get("/api/me/credits").get_json()["account"]["balance"] == 92
    assets = user.get(f"/api/projects/{pid}/assets?kind=image").get_json()["items"]
    assert assets[0]["provider"] == "openai" and assets[0]["model"] == "gpt-image-2.5-sunburst"
    with app.app_context():
        cost = db.session.query(ProviderCost).one()
        assert float(cost.estimated_usd) == 0.04 and cost.provider_reported["usage"]["output_tokens"] == 1000
    admin = make_user(admin=True)
    rows = admin.get("/api/admin/provider-costs").get_json()["rows"]
    assert rows == [{"provider": "openai", "model": "gpt-image-2.5-sunburst", "outcome": "completed",
                     "absorbed_by_aszda": False, "jobs": 1, "estimated_usd": "0.040000",
                     "jobs_with_estimate": 1, "credits_charged": 8}]


def test_image_moderation_refunds_without_cost(app, make_user, cfg, monkeypatch):
    cfg(OPENAI_API_KEY="k")
    add_prices({"openai:gpt-image-2.5-sunburst": price(images_medium=8000)})
    monkeypatch.setattr(httpx, "post", _image_response(400, {"error": {"code": "moderation_blocked"}}))
    user = make_user(credits=100)
    job = user.post("/api/generation-jobs", headers=idem(), json={
        "kind": "image", "params": {"prompt": "x"}}).get_json()["job"]
    job = user.get(f"/api/generation-jobs/{job['id']}").get_json()["job"]
    assert job["status"] == "failed" and job["error"]["code"] == "content_refused"
    assert user.get("/api/me/credits").get_json()["account"]["balance"] == 100
    with app.app_context():
        assert db.session.query(ProviderCost).count() == 0


def test_google_video_job_end_to_end_with_credits(app, make_user, cfg, google):
    cfg(AI_VIDEO_PROVIDER="google")
    add_prices({"google:veo-test-model": price(video_seconds_720p=10_000, video_seconds_1080p=12_000)})
    google.operations_queue = [done_op(videos=[pytypes.SimpleNamespace(video=pytypes.SimpleNamespace(
        uri="https://generativelanguage.googleapis.com/v1beta/files/v", video_bytes=None, mime_type="video/mp4"))])]
    user = make_user(credits=200)
    job = user.post("/api/generation-jobs", headers=idem(), json={
        "kind": "video", "params": {"prompt_text": "A fox runs", "duration": 6}}).get_json()["job"]
    job = user.get(f"/api/generation-jobs/{job['id']}").get_json()["job"]
    assert job["status"] == "completed" and job["provider"] == "google" and job["credits_charged"] == 60
    assert user.get("/api/me/credits").get_json()["account"]["balance"] == 140


# ---- AI Film Director ------------------------------------------------------------------------------

@pytest.fixture()
def director_setup(app, cfg, monkeypatch):
    cfg(ANTHROPIC_API_KEY="k", OPENAI_API_KEY="k", AI_VIDEO_PROVIDER="fake-video", AI_VIDEO_FALLBACKS=[])
    add_prices({"anthropic:claude-opus-5-5": price(input_tokens=1, output_tokens=5),
                "openai:gpt-image-2.5-sunburst": price(images_medium=8000),
                "openai:gpt-4o-mini-tts": pricing.ModelPrice(credits_per_1000={"characters": 8}, minimum_credits=2)})
    fake = FakeAnthropic(json.dumps(PLAN))
    monkeypatch.setattr(AnthropicTextAdapter, "_client", lambda self: fake)

    def fake_post(url, json=None, headers=None, timeout=None):
        if url.endswith("/images/generations"):
            return _image_response()()
        return httpx.Response(200, content=b"ID3voice")
    monkeypatch.setattr(httpx, "post", fake_post)
    return fake


def test_director_plan_apply_and_generate_scene(app, make_user, director_setup):
    user = make_user(credits=500)
    pid = user.post("/api/projects", json={"title": "Fox film"}).get_json()["project"]["id"]
    response = user.post(f"/api/projects/{pid}/director/plan", headers=idem(),
                         json={"idea": "A fox who sells shoes at the market"})
    assert response.status_code == 201, response.get_json()
    plan_job = user.get(f"/api/generation-jobs/{response.get_json()['job']['id']}").get_json()["job"]
    assert plan_job["status"] == "completed" and plan_job["provider"] == "anthropic"

    applied = user.post(f"/api/projects/{pid}/director/apply", json={"job_id": plan_job["id"]})
    assert applied.status_code == 201
    scenes = applied.get_json()["scenes"]
    assert [s["title"] for s in scenes] == ["Market", "Night"]
    assert scenes[0]["ai_prompts"]["image_prompt"].startswith("A red fox")
    again = user.post(f"/api/projects/{pid}/director/apply", json={"job_id": plan_job["id"]})
    assert again.status_code == 409 and again.get_json()["error"]["code"] == "plan_already_applied"

    key = {"Idempotency-Key": f"scene-{uuid.uuid4()}"}
    url = f"/api/projects/{pid}/director/scenes/{scenes[0]['id']}/generate"
    result = user.post(url, headers=key, json={"kinds": ["image", "voice"]})
    assert result.status_code == 202, result.get_json()
    by_kind = {r["kind"]: r for r in result.get_json()["results"]}
    assert by_kind["image"]["provider"] == "openai" and by_kind["voice"]["model"] == "gpt-4o-mini-tts"
    # The image became the scene's storyboard frame; the video then starts from it.
    with app.app_context():
        scene = db.session.get(Scene, uuid.UUID(scenes[0]["id"]))
        assert scene.preview_asset_id is not None
        frame = scene.preview_asset_id
    video = user.post(url, headers={"Idempotency-Key": f"scene-{uuid.uuid4()}"}, json={"kinds": ["video"]})
    video_job = video.get_json()["results"][0]
    with app.app_context():
        job = db.session.get(GenerationJob, uuid.UUID(video_job["job_id"]))
        assert job.provider == "fake-video" and job.input_params["reference_asset_id"] == str(frame)
        assert job.input_params["duration"] == 10 and job.scene_id == uuid.UUID(scenes[0]["id"])
    # Repeating the same request (same key) starts nothing new and charges nothing more.
    balance = user.get("/api/me/credits").get_json()["account"]["balance"]
    repeat = user.post(url, headers=key, json={"kinds": ["image", "voice"]}).get_json()["results"]
    assert all(r["created"] is False for r in repeat)
    assert user.get("/api/me/credits").get_json()["account"]["balance"] == balance
    # A scene without narration or dialogue has no voice to generate.
    night = user.post(f"/api/projects/{pid}/director/scenes/{scenes[1]['id']}/generate",
                      headers=idem(), json={"kinds": ["voice"]}).get_json()["results"]
    assert "skipped" in night[0]


def test_director_respects_ownership_and_credits(app, make_user, director_setup):
    owner, other = make_user(credits=500), make_user(credits=500)
    pid = owner.post("/api/projects", json={"title": "Mine"}).get_json()["project"]["id"]
    plan = owner.post(f"/api/projects/{pid}/director/plan", headers=idem(),
                      json={"idea": "A fox who sells shoes at the market"}).get_json()["job"]
    owner.post(f"/api/projects/{pid}/director/apply", json={"job_id": plan["id"]})
    scene_id = owner.get(f"/api/projects/{pid}").get_json()["project"]["scenes"][0]["id"] \
        if "scenes" in owner.get(f"/api/projects/{pid}").get_json()["project"] else None
    assert other.post(f"/api/projects/{pid}/director/plan", headers=idem(),
                      json={"idea": "Steal this project please"}).status_code == 404
    assert other.post(f"/api/projects/{pid}/director/apply", json={"job_id": plan["id"]}).status_code == 404
    with app.app_context():
        scene_id = scene_id or str(db.session.query(Scene).filter_by(project_id=uuid.UUID(pid)).first().id)
    assert other.post(f"/api/projects/{pid}/director/scenes/{scene_id}/generate", headers=idem(),
                      json={"kinds": ["image"]}).status_code == 404
    assert other.get(f"/api/generation-jobs/{plan['id']}").status_code == 404
    # Another user's plan job cannot be applied to your own project.
    their_pid = other.post("/api/projects", json={"title": "Theirs"}).get_json()["project"]["id"]
    assert other.post(f"/api/projects/{their_pid}/director/apply", json={"job_id": plan["id"]}).status_code == 404

    poor = make_user(credits=1)
    poor_pid = poor.post("/api/projects", json={"title": "P"}).get_json()["project"]["id"]
    response = poor.post(f"/api/projects/{poor_pid}/director/plan", headers=idem(),
                         json={"idea": "A fox who sells shoes at the market"})
    assert response.status_code == 402
