# AI providers

ASZDA talks to AI vendors only through adapters in `backend/app/providers/`. Each adapter declares:
- its models and what kind of work each does (text, image, video, speech);
- the settings each model really supports;
- how to estimate usage (the credit reservation);
- how to submit, poll and cancel a job;
- which settings it needs;
- a connection test that generates nothing.

The **orchestrator** (`backend/app/services/orchestrator.py`) decides which adapter handles a request.

| Provider | Adapter | Offers | Credential(s) |
|---|---|---|---|
| Anthropic | `anthropic_text.py` | Text: scripts, story development, characters, scene breakdowns, AI Film Director plans (structured JSON) | `ANTHROPIC_API_KEY` |
| OpenAI | `openai_speech.py` + `openai_image.py` | Voice (text-to-speech) and images (GPT Image) | `OPENAI_API_KEY` |
| Runway | `runway_video.py` | Video: text-to-video and image-to-video (`gen4.5`, `veo3.1_fast`) | `RUNWAYML_API_SECRET` |
| Google | `google_video.py` | Video with sound (Veo); images (Gemini image models, `google_image.py`) | `GEMINI_API_KEY`, or Vertex AI settings |

## Status: implemented, configured, tested

| | Code implemented | Automated tests (mocked provider) | Configured here | Real request succeeded |
|---|---|---|---|---|
| Anthropic text and Director plan | Yes | Yes | No key in the build environment | **Not yet.** Earlier, one live call was correctly rejected for an invalid key. |
| OpenAI voice | Yes | Yes | No | Not yet |
| OpenAI images | Yes | Yes | No | Not yet |
| Runway video | Yes | Yes | No | Not yet |
| Google Veo video | Yes | Yes | No | Not yet. See the model warning below. |

"Implemented" means the code and tests exist. It does **not** mean a real generation has been
produced. After adding a key, run the connection test and the manual live tests (below).

## When a model can be used

A model is offered for paid generation only when **all** of these are true:
1. The provider's settings are complete. Admin → Providers lists missing variable **names**, never values.
2. The provider is not switched off (`ASZDA_DISABLED_PROVIDERS`).
3. The model has a credit price (Admin → Pricing or the pricing file).
4. The provider has not retired the model (a retirement date is set for OpenAI TTS).

A missing key never crashes anything: the provider shows as "Not configured" and its models are unavailable.

## Routing (the orchestrator)

- **Choosing the provider.** The user, or the studio's model picker, may pick a provider and model; exactly that is used. If it cannot run, the request is refused with the reason, and there is **no silent switch**.
- **When nobody picks.** `ASZDA_AI_TEXT_PROVIDER`, `_IMAGE_`, `_VIDEO_` and `_VOICE_` choose the provider, using its default model.
- **Fallback.** If that provider cannot run, the providers in `ASZDA_AI_<KIND>_FALLBACKS` are tried in order. Only providers that offer that kind of work are candidates. The choice is stored on the job (`usage.routing`: requested, chosen, fallback used, skipped with reasons).
- **No fallback after a failure.** Fallback happens only before the job is created. A job that fails at its provider is never resent to another provider, so a request can never be billed twice.
- **Provenance.** Every generated asset records `provider` and `model`. Different providers can be used in the same project.
- **Checking the routing.** `GET /api/ai/capabilities` shows what each kind of work would use now. Admin → Providers shows it as well.

## Health checks (Admin → Providers)

For each provider the page shows:
- whether its credentials and required settings are present (names only);
- whether it is switched on;
- its capabilities and configured models, including priced, default and deprecated;
- the last connection test: when it ran, the result, the last success and the latest error.

**Test connection** runs only when an admin clicks it. It never generates anything:

| Provider | Test |
|---|---|
| Anthropic | `GET /v1/models/{id}` for each configured model |
| OpenAI | `GET /v1/models/{id}` for the default voice and image models |
| Runway | `GET /v1/organization`, which returns the API credit balance |
| Google | `models.get` for each configured Veo model |

None of the providers documents a charge for these lookups. None of them explicitly says they are
free either. A test that a provider documents as billable must be confirmed before it runs
(`connection_test_may_charge`); none is marked that way today.

## Setup, provider by provider

After changing `.env`, restart **both** the API and the worker (`docker compose up -d api worker`).
Then open Admin → Providers → Test connection, and set credit prices in Admin → Pricing.

### Anthropic (you already have this key)

1. Create a key at console.anthropic.com → API keys.
2. Set `ANTHROPIC_API_KEY=` in `.env`.
3. Optional: set `ASZDA_ANTHROPIC_TEXT_MODELS` (comma-separated; the first is the default; default `claude-opus-5-5`).
4. Price `anthropic:claude-opus-5-5` (the approved proposal already includes it).

Details:
- Uses the official `anthropic` SDK (Messages API).
- Requests opt in to the server-side refusal fallback (`fallbacks: "default"`). A refusal fails the job and charges only the tokens Anthropic reports.
- Director plans use structured outputs (`output_config.format` with a JSON schema), and scene lengths are clamped to 4–10 s. A plan cut off by the length limit fails as `incomplete_plan`; its tokens were used, so they are charged.
- Usage metrics: `input_tokens`, `output_tokens`. `max_tokens` caps all output, so the reservation is a true upper bound.

### OpenAI (voice and images)

1. Create a key at platform.openai.com → API keys.
2. Set `OPENAI_API_KEY=`. Image generation may require organization verification in OpenAI's dashboard.
3. Optional settings:
   - `ASZDA_OPENAI_TTS_MODEL` (default `gpt-4o-mini-tts`);
   - `ASZDA_OPENAI_IMAGE_MODELS` (default `gpt-image-2.5-sunburst,gpt-image-2`);
   - `ASZDA_OPENAI_IMAGE_MODEL` (default `gpt-image-2.5-sunburst`).
4. Price the voice models (approved) and the image models. **Image credit prices are not set yet.**

Voice: `POST /v1/audio/speech`
- **All OpenAI TTS models are deprecated, with shutdown on 2027-01-06**: `tts-1`, `tts-1-hd`, `gpt-4o-mini-tts` and its dated snapshots. Source: OpenAI's deprecations page, read through search summaries on 2026-10-22.
- ASZDA shows the deprecation and refuses the models from that date.
- OpenAI's suggested successor (`gpt-realtime-2.1-mini`) uses the Realtime API, not `/v1/audio/speech`. It is **not implemented**. A new voice adapter is needed before January 2027.
- Voices: `tts-1` and `tts-1-hd` have 9 (alloy, ash, coral, echo, fable, onyx, nova, sage, shimmer). `gpt-4o-mini-tts` adds ballad, verse, marin and cedar. ASZDA validates the voice per model; the default is marin, or alloy for the older models.
- Speaking-style instructions work only with `gpt-4o-mini-tts`.

Images: `POST /v1/images/generations`, using the request shape from the official `openai-python` SDK 3.36.1
- Models: `gpt-image-2.5-sunburst` (OpenAI's recommended model per its DALL-E page, search summary), `gpt-image-2`, and others via the setting. DALL-E was retired on 2026-05-12 and is not offered.
- Settings: size 1024×1024, 1536×1024 or 1024×1536; quality low, medium or high; PNG, JPEG or WebP; background auto, opaque or transparent. A transparent background needs PNG or WebP.
- Usage metrics for credits: `images_low`, `images_medium`, `images_high` (one image per job).
- OpenAI bills images by tokens. Its reported token usage is stored with each job (`provider_costs.provider_reported`).
- **Image prices are not confirmed.**
  - gpt-image-2.5: about $30 per 1M image-output tokens (search summary).
  - gpt-image-1.5 per-image prices: $0.009–$0.20, depending on size and quality (search summary).
  - Tokens per image for gpt-image-2 and 2.5: not confirmed.
- A `moderation_blocked` error fails the job as `content_refused`, and the customer is fully refunded.

### Runway (video)

1. Create a key at dev.runwayml.com and add API credits. These are separate from Runway web-app credits.
2. Set `RUNWAYML_API_SECRET=`. Optional: `ASZDA_RUNWAY_VIDEO_MODEL` (`gen4.5` or `veo3.1_fast`).
3. Price both models (approved).

Details:
- Base URL `https://api.dev.runwayml.com`, header `X-Runway-Version: 2024-11-06`. Model IDs and parameters were rechecked against the official `runwayml` SDK on 2026-10-22.
- Jobs are asynchronous: `POST /v1/text_to_video` or `POST /v1/image_to_video`, then `GET /v1/tasks/{id}`, which ASZDA polls. `DELETE` cancels.
- Runway offers no webhooks that ASZDA uses.
- **Safety blocks** (`failureCode` starting with `SAFETY.`): Runway charges for moderated generations. The customer gets a full refund. The Runway charge is recorded as an ASZDA cost (`provider_costs`, `absorbed_by_aszda`, audited). The job cannot be retried unchanged.
- **Price to verify**: Runway's pricing page says gen4.5 costs 12 credits/s ($0.12/s), but its models page says "from $0.15/s" (search summaries). The approved credit price assumes $0.12/s.

### Google Veo (video)

> **Read this first.** On 2026-10-22, Google's docs (read through search summaries) listed the
> Gemini API Veo 3.1 **preview** models with a shutdown date of that same day:
> `veo-3.1-generate-preview`, `veo-3.1-fast-generate-preview` and `veo-3.1-lite-generate-preview`.
> The replacement named is "Gemini Omni Flash", whose API is not documented as Veo-compatible.
> The GA model `veo-3.1-generate-001` was listed only for **Vertex AI**. So ASZDA ships **no
> default Veo model**: you choose the model IDs your account can actually use.

Option A, Gemini API:
1. Create a key in Google AI Studio and set `GEMINI_API_KEY=`.
2. Set `ASZDA_GOOGLE_VIDEO_MODELS=` to the model IDs to offer, and optionally `ASZDA_GOOGLE_VIDEO_MODEL=` as the default.
3. Run Test connection. It looks up each model and fails clearly if the model does not exist for your key.

Option B, Vertex AI (Google Cloud):
1. Set `GOOGLE_GENAI_USE_VERTEXAI=true`, `GOOGLE_CLOUD_PROJECT=` and `GOOGLE_CLOUD_LOCATION=`, for example `us-central1`.
2. Give the API and worker Google Cloud credentials. Usually `GOOGLE_APPLICATION_CREDENTIALS=/run/secrets/gcp.json` points to a service-account key with the Vertex AI User role, mounted into both containers. Never commit it.
3. Set `ASZDA_GOOGLE_VIDEO_MODELS=veo-3.1-generate-001` (or the models you enable), then run Test connection.

Details:
- Uses the official `google-genai` SDK (2.32.0): `models.generate_videos`, `operations.get` and `files.download`. Videos returned inline (`video_bytes`, as on Vertex) are stored directly.
- Vertex results that come back only as a Cloud Storage link are not downloaded; the job fails clearly.
- Settings:
  - prompt, negative prompt, optional first-frame image;
  - aspect ratio 16:9 or 9:16;
  - duration 4, 6 or 8 s, and resolution 720p or 1080p (1080p only with 8 s);
  - people (adults only, none, or all for text-to-video only; some regions allow adults only).
- The Gemini API rejects `seed`, `generate_audio` and `fps`, so they are not offered. Veo 3.x adds audio itself.
- Usage metrics: `video_seconds_720p`, `video_seconds_1080p`.

### Google images (Gemini image models, "Nano Banana")

The default image provider. It uses the same Google credential as Veo.

> Imagen is **not** used. Google's deprecations page (read through search summaries on
> 2026-10-28) lists the Imagen 4 models as shut down in the Gemini API on 2026-08-17, with the
> Gemini image models as the replacement. ASZDA ships **no default image model ID**.

1. Set `GEMINI_API_KEY=` (or the Vertex AI settings above).
2. List the image models your key can use: `flask --app wsgi aszda google-models` (nothing is generated).
3. Set `ASZDA_GOOGLE_IMAGE_MODELS=` to the IDs to offer, and optionally `ASZDA_GOOGLE_IMAGE_MODEL=` as the default.
4. Add a credit price for each model (`images_1k`, `images_2k`, `images_4k`), then run Test connection.

Details:
- `models.generate_content` with `response_modalities=["IMAGE"]` and `image_config` (aspect ratio and size), checked against the `google-genai` 2.32.0 source.
- Settings: prompt; shape 1:1, 16:9, 9:16, 4:3, 3:4, 3:2, 2:3 or 21:9; resolution 1K, 2K or 4K. People and output-format settings are Vertex-only in the SDK, so they are not offered.
- Draft ("thought") images some models return are skipped; the final image is stored.
- Safety refusals (`prompt_feedback.block_reason`, or a finish reason such as `IMAGE_SAFETY`) fail the job as `content_refused` with a full refund. Google does not document a charge for these, so no cost is assumed.
- Google bills image output by tokens; the `usage_metadata` it reports is kept with each job for cost reconciliation.
- Usage metrics: `images_1k`, `images_2k`, `images_4k`.
- Search-summary prices (paid tier, per second): Veo 3.1 $0.40; Veo 3.1 Fast $0.10 (720p), $0.12 (1080p); Veo 3.1 Lite $0.05/$0.08. Check them against the price for the model you enable.
- **Credit prices are not set** for any Google model.
- Safety-filtered results (`rai_media_filtered_count`) fail as `content_refused` with a full refund. Google does not document charging for them, so no ASZDA cost is assumed.
- Not implemented: cancelling a running operation, video extension, reference images, last-frame interpolation, 4k.

## Make my film (automatic films)

`POST /api/projects/{id}/director/films` runs the whole Director in the background
(`app/services/film_service.py`):

1. Claude plans the film; the plan is added to the project.
2. ASZDA estimates every remaining step and checks the balance. If it is not enough, the film
   waits (`waiting_for_credits`) until the user adds credits and clicks Continue.
3. For every scene: the image, then a video that starts from that image, and the voice. Each is
   an ordinary generation job (credits reserved first, refunded on failure); the usual limit of
   running jobs per user applies, so steps start as earlier ones finish.
4. `app/services/film_assembly.py` joins the clips and voices with ffmpeg into one MP4 (16:9
   1280×720 or 9:16 720×1280, 24 fps, H.264 + AAC) and saves it to the project. Joining costs no
   credits. If a voice is longer than its clip, the last frame is held.

The film moves on when any of its jobs finishes, and Celery beat checks unfinished films every
minute (`advance-films`), so a lost wake-up only delays it. ffmpeg is installed in the API image.

## Checking providers from the command line (free)

```bash
flask --app wsgi aszda providers-test            # every provider; or: ... providers-test anthropic
# with Docker:
docker compose exec api flask --app wsgi aszda providers-test
```

This runs the same free connection tests as Admin -> Providers and stores the results.

## Manual live tests (after adding credentials)

`backend/tests_live/` holds opt-in tests that call the real APIs. The normal test run skips them.

```bash
cd backend
ASZDA_LIVE_TESTS=1 .venv/bin/python -m pytest tests_live -q -s                       # free: connection checks
ASZDA_LIVE_TESTS=1 ASZDA_LIVE_PAID=1 .venv/bin/python -m pytest tests_live -q -s -k anthropic   # PAID, small
```

- **Paid tests are billed by the provider.** Run them one provider at a time with `-k anthropic`, `openai`, `runway` or `google`.
- They use the smallest settings: a short Claude reply and a short Director plan, one low-quality image, one short voice clip, a 2-second Runway clip, and a 4-second Veo clip.
- Outputs go to `backend/live-test-output/`, which is git-ignored.
- **Inside Docker**, the production image has no pytest, so install it for the app user first:
  `docker compose exec api sh -c "pip install --user -q pytest && ASZDA_LIVE_TESTS=1 python -m pytest tests_live -q -s -p no:cacheprovider -o cache_dir=/tmp"`.

## Adding or replacing a provider

1. Write an adapter that subclasses `ProviderAdapter` in `backend/app/providers/base.py`. It provides:
   - `model_specs`, `estimate_usage` and `submit`;
   - `poll` and `cancel` if it is asynchronous;
   - `missing_settings`, `test_connection` and `params_for_brief` (used by the Director).
2. Register it in `registry.py`.
3. Add its credit prices and, if it should be a default, its `ASZDA_AI_*_PROVIDER` setting.

Nothing else in the application needs to change.
