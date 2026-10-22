"""MANUAL live tests against the real provider APIs. Not part of the normal test run.

They use the API keys from your environment and are skipped unless you opt in:

    ASZDA_LIVE_TESTS=1 python -m pytest tests_live -q -s            # free checks only
    ASZDA_LIVE_TESTS=1 ASZDA_LIVE_PAID=1 python -m pytest tests_live -q -s -k anthropic
                                                                    # also small PAID generations

Free checks call the same model/account lookups as Admin -> Providers -> Test connection.
Tests marked PAID generate real output and are billed by the provider (smallest settings:
a short Claude reply, one low-quality image, a short voice clip, the shortest video). Run
them one provider at a time with -k. Outputs are written to ./live-test-output/.
No database is needed: adapters are called directly.
"""

import os
import time
import uuid
from pathlib import Path

import pytest

from app import create_app
from app.providers.anthropic_text import AnthropicTextAdapter
from app.providers.base import JobContext
from app.providers.google_video import GoogleVideoAdapter
from app.providers.openai_speech import OpenAIAdapter
from app.providers.runway_video import RunwayVideoAdapter

pytestmark = pytest.mark.skipif(os.environ.get("ASZDA_LIVE_TESTS") != "1",
                                reason="live provider tests are opt-in (ASZDA_LIVE_TESTS=1)")
paid = pytest.mark.skipif(os.environ.get("ASZDA_LIVE_PAID") != "1",
                          reason="PAID test: set ASZDA_LIVE_PAID=1 to run (billed by the provider)")
OUT = Path("live-test-output")


@pytest.fixture(scope="module")
def app_ctx():
    app = create_app("development")
    with app.app_context():
        yield app


def need(adapter):
    missing = adapter.missing_settings()
    if missing:
        pytest.skip(f"{adapter.label} not configured: {', '.join(missing)}")
    return adapter


def run(adapter, kind, params, poll_limit_s=900):
    spec = adapter.default_model(kind)
    clean = adapter.validate(spec, params)
    ctx = JobContext(job_id=uuid.uuid4(), model=spec.id, params=clean, provider_job_id=None,
                     load_asset=lambda _id: pytest.fail("no reference assets in live tests"))
    outcome = adapter.submit(ctx)
    deadline = time.time() + poll_limit_s
    while outcome.status == "pending":
        assert time.time() < deadline, "provider took too long"
        time.sleep(10)
        ctx.provider_job_id = outcome.provider_job_id
        outcome = adapter.poll(ctx)
    OUT.mkdir(exist_ok=True)
    for i, output in enumerate(outcome.outputs):
        data = output.data if output.data is not None else output.open_stream().read()
        path = OUT / f"{adapter.name}-{spec.id}-{i}.{output.mime_type.split('/')[-1]}"
        path.write_bytes(data)
        print(f"\n{adapter.label}: wrote {path} ({len(data)} bytes); usage {outcome.usage}")
    return outcome


# ---- Free: credential and model checks ------------------------------------------------------

@pytest.mark.parametrize("adapter_cls", [AnthropicTextAdapter, OpenAIAdapter, RunwayVideoAdapter,
                                         GoogleVideoAdapter])
def test_connection(app_ctx, adapter_cls):
    adapter = need(adapter_cls())
    print(f"\n{adapter.label}: {adapter.test_connection()}")


# ---- PAID: smallest real generations ----------------------------------------------------------

@paid
def test_anthropic_text(app_ctx):
    from app.models import GenerationKind

    outcome = run(need(AnthropicTextAdapter()), GenerationKind.TEXT,
                  {"task": "freeform", "prompt": "Write one sentence about a fox.", "max_output_tokens": 500,
                   "effort": "low"})
    assert outcome.result["text"]


@paid
def test_anthropic_director_plan(app_ctx):
    from app.models import GenerationKind

    outcome = run(need(AnthropicTextAdapter()), GenerationKind.TEXT,
                  {"task": "director_plan", "prompt": "A 3-scene film about a fox who sells shoes.",
                   "max_output_tokens": 6000, "effort": "low"})
    assert outcome.result["plan"]["scenes"]


@paid
def test_openai_image(app_ctx):
    from app.models import GenerationKind

    run(need(OpenAIAdapter()), GenerationKind.IMAGE, {"prompt": "A red fox, watercolour", "quality": "low"})


@paid
def test_openai_speech(app_ctx):
    from app.models import GenerationKind

    run(need(OpenAIAdapter()), GenerationKind.SPEECH, {"text": "Hello from ASZDA Studio."})


@paid
def test_runway_video(app_ctx):
    from app.models import GenerationKind

    run(need(RunwayVideoAdapter()), GenerationKind.VIDEO,
        {"mode": "text_to_video", "prompt_text": "A red fox walks through snow", "ratio": "1280:720", "duration": 2})


@paid
def test_google_video(app_ctx):
    from app.models import GenerationKind

    run(need(GoogleVideoAdapter()), GenerationKind.VIDEO,
        {"prompt_text": "A red fox walks through snow", "duration": 4, "resolution": "720p"})
