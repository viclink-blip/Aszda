# AI providers

ASZDA talks to AI vendors only through adapters in `backend/app/providers/`. Each adapter
declares its models, the kind of output (text, speech, video...), the settings each model really
supports, how to estimate usage, and how to submit/poll/cancel.

A model is **available** to users only when both are true:
1. its API key environment variable is set, and
2. it has a credit price in the pricing file (see [CREDITS.md](CREDITS.md)).

`flask --app wsgi aszda check-pricing` shows the state of every model.

## How the facts were verified (2026-10-21)
The vendors' documentation websites could not be opened from the build environment. Facts were
taken from each vendor's **official SDK source code** on GitHub (generated from their API specs):
`anthropics` SDK bundled guidance for Claude, `openai/openai-python`, `runwayml/sdk-python`.
Anything not confirmed is listed below. **Before going live, re-check against the vendors'
current documentation** and run one real job per model in staging.

## Anthropic Claude — `anthropic_text.py`
- Uses the official `anthropic` Python SDK (Messages API), credential `ANTHROPIC_API_KEY`.
- Model: `claude-opus-5-5` by default (`ASZDA_ANTHROPIC_TEXT_MODELS` to change).
- Tasks: story concept, script draft, character sheet, scene breakdown, free prompt.
- Settings: task, prompt (≤ 12,000 chars), maximum output tokens (500–16,000), effort (low/medium/high).
- Requests opt in to Anthropic's server-side refusal fallback (`fallbacks: "default"`, beta
  `server-side-fallback-2026-07-01`). A refusal (`stop_reason: "refusal"`) fails the job and
  charges only the usage Anthropic reports.
- Usage metrics: `input_tokens`, `output_tokens`. `max_tokens` caps all output, so the estimate
  is a true upper bound.
- Verified live in this build: a job travelled through the real queue and reached Anthropic's API,
  which rejected a deliberately invalid key (401) → job failed and credits were refunded.
  A successful generation has **not** been run (no key was available).

## OpenAI text-to-speech — `openai_speech.py`
- `POST https://api.openai.com/v1/audio/speech`, `Authorization: Bearer $OPENAI_API_KEY`.
- Models: `gpt-4o-mini-tts`, `tts-1`, `tts-1-hd`. Voices: alloy, ash, ballad, coral, echo, sage,
  shimmer, verse, marin, cedar, fable, onyx, nova. Formats offered: mp3, wav, opus, aac, flac.
  Speed 0.25–4.0. Input ≤ 4,096 characters. `instructions` only for `gpt-4o-mini-tts`.
- Usage metric: `characters`.
- **Not verified**: which voices each model supports (OpenAI says availability can differ by model);
  the default output format. Provider USD pricing is not configured.
- Voice cloning is not offered and must not be added without consent and safeguards.

## Runway video — `runway_video.py`
- Base URL `https://api.dev.runwayml.com`, `Authorization: Bearer $RUNWAYML_API_SECRET`,
  header `X-Runway-Version: 2024-11-06`.
- `POST /v1/text_to_video`, `POST /v1/image_to_video`, `GET /v1/tasks/{id}`, `DELETE /v1/tasks/{id}`.
- Models offered:
  - `gen4.5`: prompt required (≤ 1,000 chars), duration 2–10 s; ratios 1280:720 / 720:1280
    (text) and also 1104:832, 832:1104, 960:960, 1584:672 (image).
  - `veo3.1_fast`: ratios 1280:720, 720:1280, 1080:1920, 1920:1080; duration 4/6/8 s; optional audio.
- Reference images are sent as base64 data URIs (≤ 5 MB, PNG/JPEG/WebP).
- Task statuses: PENDING, THROTTLED, RUNNING, SUCCEEDED (output = list of URLs), FAILED, CANCELLED.
  Polled every `ASZDA_PROVIDER_POLL_SECONDS` (Runway asks for ≥ 5 s). Outputs are downloaded over
  HTTPS (streamed, size-capped) into ASZDA storage because Runway's URLs are temporary.
- Usage metrics: `video_seconds`, `video_seconds_with_audio`.
- **Not verified**: the exact create-response shape (the adapter requires an `id` and fails clearly
  otherwise); Runway's credit prices (search results suggested gen4.5 ≈ 12 credits/s and
  veo3.1_fast ≈ 10–15 credits/s, 1 credit = $0.01 — confirm on Runway's pricing page).

## Considered and not built
- **OpenAI Sora (video)**: OpenAI's SDK marks the Videos API deprecated with shutdown on
  2026-09-24 — already past at build time.
- **ElevenLabs (voice)**: endpoints were confirmed but the current model list conflicted between
  sources; add once verified.
- **Image generation**: no provider chosen yet.

## Adding a provider
1. Read the vendor's official docs. Do not guess endpoints, model IDs or parameters.
2. Create `app/providers/<vendor>_<kind>.py` subclassing `ProviderAdapter`:
   `model_specs()`, a pydantic params model + `SettingField`s, `estimate_usage()` (upper bound),
   `submit()`, and `poll()`/`cancel()` if the vendor is asynchronous. Map errors to
   `ProviderError(retryable=...)` with `classify_http_status`.
3. Register it in `app/providers/registry.py`.
4. Add the credential to `.env.example` and `docs/ENVIRONMENT.md`, and prices to the pricing file.
5. Add unit tests with mocked HTTP in `tests/test_providers.py` (never call the paid API in tests).
