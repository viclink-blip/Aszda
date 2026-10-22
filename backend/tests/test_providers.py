"""Unit tests for the real provider adapters. HTTP and SDK calls are mocked;
nothing is sent to Anthropic, OpenAI or Runway."""

import uuid
from types import SimpleNamespace

import httpx
import pytest
from pydantic import ValidationError

from app.providers.anthropic_text import AnthropicTextAdapter
from app.providers.base import JobContext, ProviderError
from app.providers.openai_speech import OpenAISpeechAdapter
from app.providers.runway_video import RunwayVideoAdapter
from tests.conftest import PNG
from tests.fakes import MP4


def ctx(model, params, provider_job_id=None, assets=None):
    def load_asset(asset_id):
        return assets[asset_id]

    return JobContext(job_id=uuid.uuid4(), model=model, params=params,
                      provider_job_id=provider_job_id, load_asset=load_asset)


@pytest.fixture()
def app_ctx(app):
    with app.app_context():
        yield app


# ---- Anthropic ----------------------------------------------------------------------

class FakeMessages:
    def __init__(self, response=None, error=None):
        self.response, self.error, self.kwargs = response, error, None

    def create(self, **kwargs):
        self.kwargs = kwargs
        if self.error:
            raise self.error
        return self.response


def _claude_response(text="# Concept", stop_reason="end_turn"):
    return SimpleNamespace(
        content=[SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=text)],
        stop_reason=stop_reason, model="claude-opus-5-5",
        usage=SimpleNamespace(input_tokens=120, output_tokens=640))


def _with_fake_client(adapter, messages):
    adapter._client = lambda: SimpleNamespace(beta=SimpleNamespace(messages=messages))


def test_anthropic_request_shape_and_result(app_ctx):
    app_ctx.config["ANTHROPIC_API_KEY"] = "test"
    try:
        adapter = AnthropicTextAdapter()
        assert adapter.is_configured()
        spec = adapter.get_model("claude-opus-5-5")
        params = adapter.validate(spec, {"task": "script", "prompt": "A fox opens a shoe shop"})
        assert params["max_output_tokens"] == 4000 and params["effort"] == "medium"
        usage = adapter.estimate_usage(spec, params)
        assert usage["output_tokens"] == 4000 and usage["input_tokens"] > 0

        messages = FakeMessages(_claude_response())
        _with_fake_client(adapter, messages)
        outcome = adapter.submit(ctx("claude-opus-5-5", params))
        sent = messages.kwargs
        assert sent["model"] == "claude-opus-5-5"
        assert sent["max_tokens"] == 4000
        assert sent["output_config"] == {"effort": "medium"}
        assert sent["fallbacks"] == "default"
        assert sent["betas"] == ["server-side-fallback-2026-07-01"]
        assert "thinking" not in sent  # adaptive thinking is the default on this model
        assert outcome.status == "completed"
        assert outcome.result["text"] == "# Concept"
        assert outcome.usage == {"input_tokens": 120, "output_tokens": 640}
        assert outcome.outputs[0].mime_type == "text/markdown"
    finally:
        app_ctx.config["ANTHROPIC_API_KEY"] = ""


def test_anthropic_refusal_reports_usage(app_ctx):
    adapter = AnthropicTextAdapter()
    _with_fake_client(adapter, FakeMessages(_claude_response(text="", stop_reason="refusal")))
    with pytest.raises(ProviderError) as err:
        adapter.submit(ctx("claude-opus-5-5", {"task": "freeform", "prompt": "x",
                                               "max_output_tokens": 1000, "effort": "low"}))
    assert err.value.code == "content_refused"
    assert err.value.usage == {"input_tokens": 120, "output_tokens": 640}
    assert not err.value.retryable


def test_anthropic_errors_are_classified(app_ctx):
    import anthropic

    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    adapter = AnthropicTextAdapter()
    params = {"task": "freeform", "prompt": "x", "max_output_tokens": 1000, "effort": "low"}
    rate = anthropic.RateLimitError("slow down", response=httpx.Response(429, request=request), body=None)
    _with_fake_client(adapter, FakeMessages(error=rate))
    with pytest.raises(ProviderError) as err:
        adapter.submit(ctx("claude-opus-5-5", params))
    assert err.value.retryable
    auth = anthropic.AuthenticationError("bad key", response=httpx.Response(401, request=request), body=None)
    _with_fake_client(adapter, FakeMessages(error=auth))
    with pytest.raises(ProviderError) as err:
        adapter.submit(ctx("claude-opus-5-5", params))
    assert err.value.code == "provider_auth_failed" and not err.value.retryable


def test_anthropic_validation_limits(app_ctx):
    adapter = AnthropicTextAdapter()
    spec = adapter.get_model("claude-opus-5-5")
    with pytest.raises(ValidationError):
        adapter.validate(spec, {"task": "script", "prompt": ""})
    with pytest.raises(ValidationError):
        adapter.validate(spec, {"task": "poem-generator", "prompt": "x"})
    with pytest.raises(ValidationError):
        adapter.validate(spec, {"task": "script", "prompt": "x", "max_output_tokens": 100000})


# ---- OpenAI speech -----------------------------------------------------------------

def test_openai_speech_request_and_output(app_ctx, monkeypatch):
    app_ctx.config["OPENAI_API_KEY"] = "test-key"
    seen = {}

    def fake_post(url, json, headers, timeout):
        seen.update(url=url, json=json, headers=headers)
        return httpx.Response(200, content=b"ID3fake-mp3-bytes")

    monkeypatch.setattr(httpx, "post", fake_post)
    try:
        adapter = OpenAISpeechAdapter()
        spec = adapter.get_model("gpt-4o-mini-tts")
        params = adapter.validate(spec, {"text": "Habari, karibu ASZDA.", "voice": "coral",
                                         "instructions": "Warm narrator", "language": "Swahili"})
        assert "model_id" not in params
        outcome = adapter.submit(ctx("gpt-4o-mini-tts", params))
    finally:
        app_ctx.config["OPENAI_API_KEY"] = ""
    assert seen["url"] == "https://api.openai.com/v1/audio/speech"
    assert seen["headers"]["Authorization"] == "Bearer test-key"
    assert seen["json"] == {"model": "gpt-4o-mini-tts", "input": "Habari, karibu ASZDA.", "voice": "coral",
                            "response_format": "mp3", "speed": 1.0,
                            "instructions": "Warm narrator\nSpeak in Swahili."}
    assert outcome.outputs[0].mime_type == "audio/mpeg"
    assert outcome.usage == {"characters": 21}


def test_openai_speech_validation(app_ctx):
    adapter = OpenAISpeechAdapter()
    with pytest.raises(ValidationError):
        adapter.validate(adapter.get_model("tts-1"), {"text": "hi", "instructions": "whisper"})
    with pytest.raises(ValidationError):
        adapter.validate(adapter.get_model("tts-1"), {"text": "x" * 4097})
    with pytest.raises(ValidationError):
        adapter.validate(adapter.get_model("tts-1"), {"text": "hi", "voice": "darth"})
    with pytest.raises(ValidationError):
        adapter.validate(adapter.get_model("tts-1"), {"text": "hi", "speed": 9})


def test_openai_speech_errors(app_ctx, monkeypatch):
    adapter = OpenAISpeechAdapter()
    params = {"text": "hi", "voice": "alloy", "response_format": "mp3", "speed": 1.0}
    for status, retryable in ((429, True), (500, True), (401, False), (400, False)):
        monkeypatch.setattr(httpx, "post", lambda *a, _s=status, **k: httpx.Response(_s, json={}))
        with pytest.raises(ProviderError) as err:
            adapter.submit(ctx("tts-1", params))
        assert err.value.retryable is retryable


# ---- Runway -------------------------------------------------------------------------

def test_runway_validation_by_model_and_mode(app_ctx):
    adapter = RunwayVideoAdapter()
    gen = adapter.get_model("gen4.5")
    veo = adapter.get_model("veo3.1_fast")
    ok = adapter.validate(gen, {"mode": "text_to_video", "prompt_text": "A fox", "ratio": "1280:720",
                                "duration": 5})
    assert ok["duration"] == 5
    with pytest.raises(ValidationError):  # square is image-to-video only for gen4.5
        adapter.validate(gen, {"mode": "text_to_video", "prompt_text": "A fox", "ratio": "960:960"})
    with pytest.raises(ValidationError):
        adapter.validate(gen, {"mode": "text_to_video", "prompt_text": "A fox", "ratio": "1280:720",
                               "duration": 11})
    with pytest.raises(ValidationError):  # image mode needs an image
        adapter.validate(veo, {"mode": "image_to_video", "ratio": "1280:720"})
    with pytest.raises(ValidationError):  # veo durations are 4, 6 or 8
        adapter.validate(veo, {"mode": "text_to_video", "prompt_text": "x", "ratio": "1280:720",
                               "duration": 5})
    assert adapter.estimate_usage(veo, {"duration": 8, "audio": True}) == {"video_seconds_with_audio": 8}


def test_runway_submit_poll_and_cancel(app_ctx, monkeypatch):
    app_ctx.config["RUNWAY_API_KEY"] = "test-key"
    calls = []
    asset_id = uuid.uuid4()
    states = iter([
        {"id": "task-1", "status": "RUNNING", "progress": 0.4},
        {"id": "task-1", "status": "SUCCEEDED", "output": ["https://cdn.example/out.mp4"], "cost": 60},
    ])

    def fake_request(method, url, headers, timeout, json=None):
        calls.append((method, url, headers, json))
        if method == "POST":
            return httpx.Response(200, json={"id": "task-1"})
        if method == "DELETE":
            return httpx.Response(204)
        return httpx.Response(200, json=next(states))

    monkeypatch.setattr(httpx, "request", fake_request)
    try:
        adapter = RunwayVideoAdapter()
        spec = adapter.get_model("gen4.5")
        params = adapter.validate(spec, {"mode": "image_to_video", "prompt_text": "The fox waves",
                                         "reference_asset_id": str(asset_id), "ratio": "960:960",
                                         "duration": 6, "seed": 7})
        job = ctx("gen4.5", params, assets={asset_id: (PNG, "image/png")})
        outcome = adapter.submit(job)
        assert outcome.status == "pending" and outcome.provider_job_id == "task-1"
        method, url, headers, body = calls[0]
        assert url == "https://api.dev.runwayml.com/v1/image_to_video"
        assert headers["X-Runway-Version"] == "2024-11-06"
        assert headers["Authorization"] == "Bearer test-key"
        assert body["model"] == "gen4.5" and body["ratio"] == "960:960" and body["duration"] == 6
        assert body["promptText"] == "The fox waves" and body["seed"] == 7
        assert body["promptImage"].startswith("data:image/png;base64,")

        job.provider_job_id = "task-1"
        running = adapter.poll(job)
        assert running.status == "pending" and running.progress == 40
        done = adapter.poll(job)
        assert done.status == "completed"
        assert done.usage == {"video_seconds": 6}
        assert done.outputs[0].mime_type == "video/mp4" and done.outputs[0].open_stream is not None

        assert adapter.cancel(job) is True
        assert calls[-1][0] == "DELETE" and calls[-1][1].endswith("/v1/tasks/task-1")
    finally:
        app_ctx.config["RUNWAY_API_KEY"] = ""


def test_runway_failure_and_missing_task_id(app_ctx, monkeypatch):
    adapter = RunwayVideoAdapter()
    params = {"mode": "text_to_video", "prompt_text": "x", "ratio": "1280:720", "duration": 5}
    monkeypatch.setattr(httpx, "request", lambda *a, **k: httpx.Response(200, json={"unexpected": True}))
    with pytest.raises(ProviderError) as err:
        adapter.submit(ctx("gen4.5", params))
    assert err.value.code == "unexpected_provider_response"

    # Safety block: generic message (Runway asks not to show the code's detail), no retry, the
    # customer is not charged, and the usage Runway bills is marked as ASZDA's own cost.
    monkeypatch.setattr(httpx, "request", lambda *a, **k: httpx.Response(
        200, json={"status": "FAILED", "failure": "Moderation", "failureCode": "SAFETY.INPUT.TEXT"}))
    with pytest.raises(ProviderError) as err:
        adapter.poll(ctx("gen4.5", params, provider_job_id="t"))
    assert err.value.code == "content_refused" and not err.value.retryable
    assert "SAFETY" not in err.value.message and "credits were returned" in err.value.message
    assert err.value.usage == {} and err.value.absorbed_usage == {"video_seconds": 5}
    assert err.value.provider_reported == {"failureCode": "SAFETY.INPUT.TEXT", "safety_block": True}

    # Any other failure: Runway refunds it, so nothing is billed to anyone.
    monkeypatch.setattr(httpx, "request", lambda *a, **k: httpx.Response(
        200, json={"status": "FAILED", "failure": "Internal", "failureCode": "INTERNAL.BAD_OUTPUT"}))
    with pytest.raises(ProviderError) as err:
        adapter.poll(ctx("gen4.5", params, provider_job_id="t"))
    assert err.value.message == "Internal" and err.value.code == "runway_internal.bad_output"
    assert err.value.usage == {} and err.value.absorbed_usage == {}


def test_runway_download_rejects_non_https(app_ctx, monkeypatch):
    from app.providers.runway_video import _downloader

    with pytest.raises(ProviderError):
        _downloader("http://insecure.example/video.mp4")()

    class FakeStream:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        status_code = 200

        def iter_bytes(self, size):
            yield MP4

    monkeypatch.setattr(httpx, "stream", lambda *a, **k: FakeStream())
    assert _downloader("https://cdn.example/v.mp4")().read() == MP4
