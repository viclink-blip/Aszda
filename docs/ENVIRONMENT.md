# Environment variables

The backend reads settings from environment variables (and from `backend/.env` when you run it
locally — `python-dotenv` loads that file). The template with every variable is
[`.env.example`](../.env.example). **Never commit a real `.env`.**

## Core

| Variable | Default | Notes |
|---|---|---|
| `ASZDA_ENV` | `development` | `development`, `testing` (used by the test suite) or `production`. Production validates the settings below and refuses to start if they are unsafe. |
| `ASZDA_SECRET_KEY` | dev-only value | Signs file links. Production: ≥ 32 random characters. |
| `ASZDA_JWT_SECRET_KEY` | dev-only value | Signs access tokens. Production: ≥ 32 random characters, different from the secret key. |
| `DATABASE_URL` | `postgresql+psycopg://aszda:aszda@localhost:5432/aszda` | Keep the `postgresql+psycopg://` prefix. |
| `TEST_DATABASE_URL` | `...localhost:5432/aszda_test` | Used only by `pytest`. The tests wipe this database. |
| `REDIS_URL` | `redis://localhost:6379/0` | Celery broker (also `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` if you need them separate). |
| `ASZDA_FRONTEND_URL` | `http://localhost:3000` | Used to build links in emails. |
| `ASZDA_CORS_ORIGINS` | `http://localhost:3000` | Comma-separated. Only needed if the browser calls the API from another origin. |
| `ASZDA_COOKIE_SECURE` | `true` (`false` in development) | Must be `true` in production (HTTPS). |
| `ASZDA_TRUSTED_PROXIES` | `0` | How many reverse proxies that **add** the client IP sit in front of the API (nginx sending `/api` straight to Flask = 1). Do **not** count the Next.js `/api` rewrite: it only passes through a client-supplied `X-Forwarded-For`, which anyone can fake. |
| `ASZDA_CELERY_EAGER` | `false` | Development only: run jobs inside the API process. Refused in production. |
| `ASZDA_ACCESS_TOKEN_MINUTES` | `15` | Access token lifetime. |
| `ASZDA_REFRESH_TOKEN_DAYS` | `14` | How long a device stays signed in without activity. |
| `ASZDA_REFRESH_REUSE_GRACE_SECONDS` | `20` | Reusing a refresh token within this window (two tabs refreshing together) is allowed; later reuse revokes the session. |
| `ASZDA_LOG_LEVEL` | `INFO` | |

## Email

| Variable | Default | Notes |
|---|---|---|
| `ASZDA_MAIL_BACKEND` | `console` | `console` prints emails to the API log (development). `smtp` sends them (required in production). |
| `ASZDA_MAIL_FROM` | `ASZDA <no-reply@example.com>` | Use an address on your domain with SPF/DKIM set up. |
| `ASZDA_SMTP_HOST`, `ASZDA_SMTP_PORT`, `ASZDA_SMTP_USERNAME`, `ASZDA_SMTP_PASSWORD`, `ASZDA_SMTP_USE_TLS` | | From your email provider (e.g. Amazon SES, Postmark, Mailgun, Brevo). |

## Storage

| Variable | Default | Notes |
|---|---|---|
| `ASZDA_STORAGE_BACKEND` | `local` | `local` (a folder) or `s3`. |
| `ASZDA_LOCAL_STORAGE_ROOT` | `backend/var/storage` | Local folder for media. |
| `ASZDA_MAX_UPLOAD_MB` | `50` | Per file. Keep nginx `client_max_body_size` slightly above. |
| `ASZDA_SIGNED_URL_TTL_SECONDS` | `900` | How long view/download links work. |
| `ASZDA_S3_BUCKET`, `ASZDA_S3_REGION`, `ASZDA_S3_ENDPOINT_URL`, `ASZDA_S3_ACCESS_KEY_ID`, `ASZDA_S3_SECRET_ACCESS_KEY` | | For AWS S3 or compatible services (Cloudflare R2, MinIO, Wasabi). Keep the bucket private. |

## Credits and limits

| Variable | Default | Notes |
|---|---|---|
| `ASZDA_PRICING_FILE` | *(empty)* | Path to the pricing JSON. Empty = nothing is priced = no generation. See [CREDITS.md](CREDITS.md). |
| `ASZDA_SIGNUP_CREDIT_GRANT` | `50` | One-time free credits when a new account confirms its email (once per inbox; never expire). `0` turns it off. |
| `ASZDA_SIGNUP_GRANT_DAILY_CAP` | `200` | At most this many sign-up grants per UTC day (`0` = no cap). |
| `ASZDA_MAX_CREDITS_PER_JOB` | `500` | A single job costing more is refused. |
| `ASZDA_MAX_ACTIVE_JOBS_PER_USER` | `3` | Concurrent running jobs per user. |
| `ASZDA_DAILY_JOB_LIMIT` | `50` | Jobs per user per UTC day. |
| `ASZDA_MONTHLY_CREDIT_LIMIT` | `5000` | Credits per user per calendar month (UTC) for users without a plan-specific limit (set per plan in Admin → Pricing). |
| `ASZDA_REQUIRE_VERIFIED_EMAIL` | `true` | Require a confirmed email before generating. |
| `ASZDA_RATELIMIT_STORAGE_URI` | `memory://` | Use `redis://...` in production so all processes share limits. |
| `ASZDA_RATELIMIT_DEFAULT` | `300 per minute` | Default limit for every endpoint. |

## AI providers (server only)

Setup steps for each provider: [PROVIDERS.md](PROVIDERS.md).

| Variable | Provider | Notes |
|---|---|---|
| `ANTHROPIC_API_KEY` | Anthropic | From the Claude Console. |
| `ASZDA_ANTHROPIC_TEXT_MODELS` | Anthropic | Comma-separated model IDs; the first is the default. Default `claude-opus-5-5`. |
| `OPENAI_API_KEY` | OpenAI | From the OpenAI platform (voice and images). |
| `ASZDA_OPENAI_TTS_MODEL` | OpenAI | Default voice model. Default `gpt-4o-mini-tts`. All OpenAI TTS models shut down on 2027-01-06. |
| `ASZDA_OPENAI_IMAGE_MODELS` / `ASZDA_OPENAI_IMAGE_MODEL` | OpenAI | Image models offered / the default. Defaults `gpt-image-2.5-sunburst,gpt-image-2` / `gpt-image-2.5-sunburst`. |
| `RUNWAYML_API_SECRET` | Runway | From the Runway developer portal. |
| `ASZDA_RUNWAY_VIDEO_MODEL` | Runway | Default video model: `gen4.5` or `veo3.1_fast`. |
| `GEMINI_API_KEY` | Google | Gemini API key from Google AI Studio. Not needed with Vertex AI. |
| `GOOGLE_GENAI_USE_VERTEXAI`, `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION` | Google | Use Vertex AI instead of a Gemini API key. Credentials come from `GOOGLE_APPLICATION_CREDENTIALS` (a mounted service-account file) or the platform. |
| `ASZDA_GOOGLE_VIDEO_MODELS` / `ASZDA_GOOGLE_VIDEO_MODEL` | Google | Veo model IDs to offer / the default. **No default**: see PROVIDERS.md. |
| `ASZDA_AI_TEXT_PROVIDER`, `ASZDA_AI_IMAGE_PROVIDER`, `ASZDA_AI_VIDEO_PROVIDER`, `ASZDA_AI_VOICE_PROVIDER` | routing | Provider used when a request names none. Defaults: `anthropic`, `openai`, `runway`, `openai`. |
| `ASZDA_AI_TEXT_FALLBACKS`, `ASZDA_AI_IMAGE_FALLBACKS`, `ASZDA_AI_VIDEO_FALLBACKS`, `ASZDA_AI_VOICE_FALLBACKS` | routing | Comma-separated providers tried in order if the preferred one is not ready. Default for video: `google`. |
| `ASZDA_DISABLED_PROVIDERS` | routing | Providers switched off even with a key, for example `google`. |
| `ASZDA_PROVIDER_POLL_SECONDS` | | How often to check asynchronous jobs (default 10; Runway asks for ≥ 5). |
| `ASZDA_PROVIDER_MAX_POLL_MINUTES` | | Give up (and refund) after this long (default 30). |
| `ASZDA_STUCK_QUEUED_MINUTES` | `30` | A job still queued after this long (lost queue message) is failed and refunded by the sweeper. |
| `ASZDA_STUCK_RUNNING_MINUTES` | `45` | A running job with no provider task after this long (crashed worker) is failed and refunded. |

## Billing and payments (see [BILLING.md](BILLING.md))

| Variable | Default | Notes |
|---|---|---|
| `ASZDA_USD_TO_KES_REFERENCE_RATE` | `133` | Fixed business reference rate for the labelled KES amounts. Never used to charge. |
| `ASZDA_BILLING_CATALOG_FILE` | `backend/billing_catalog.json` | Plans and credit packages (prices in US cents). |
| `PAYSTACK_SECRET_KEY` | *(empty)* | `sk_test_...` or `sk_live_...`. Empty = payments off. Server only. |
| `ASZDA_PAYSTACK_USD_ENABLED` | `false` | Set to `true` only after confirming the Paystack account accepts and settles USD. |
| `ASZDA_PAYMENT_FEE_PERCENT` | `3.8` | Card fee assumed in Admin → Pricing margin reports (Paystack Kenya international card rate). |
| `ASZDA_ALLOW_TEST_PAYMENTS` | `false` | Production refuses a test key unless this is `true` (staging only). |

## Frontend

| Variable | Default | Notes |
|---|---|---|
| `ASZDA_API_URL` | `http://localhost:5000` | Where the Next.js server forwards `/api/*`. Put it in `frontend/.env.local`. |
