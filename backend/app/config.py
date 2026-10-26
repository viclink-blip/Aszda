"""Application configuration.

All settings come from environment variables so that the same code runs in
development, testing and production. See docs/ENVIRONMENT.md for every variable.
"""

from __future__ import annotations

import os
from datetime import timedelta

# Prefixes of the variables ASZDA reads. A value that starts with "#" is a comment that ended up
# in the value (Docker Compose does not strip a comment written after an empty value, e.g.
# `PAYSTACK_SECRET_KEY=   # sk_test_...`), so it is treated as not set.
_OWN_PREFIXES = ("ASZDA_", "PAYSTACK_", "ANTHROPIC_", "OPENAI_", "RUNWAYML_", "GEMINI_", "GOOGLE_",
                 "DATABASE_URL", "TEST_DATABASE_URL", "REDIS_URL", "CELERY_")


def _drop_comment_values() -> None:
    for name, value in list(os.environ.items()):
        if name.startswith(_OWN_PREFIXES) and value.strip().startswith("#"):
            os.environ[name] = ""


_drop_comment_values()


def _bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    value = os.environ.get(name)
    return int(value) if value not in (None, "") else default


def _list(name: str, default: str = "") -> list[str]:
    raw = os.environ.get(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


class BaseConfig:
    ENV_NAME = "base"
    TESTING = False

    SECRET_KEY = os.environ.get("ASZDA_SECRET_KEY", "")
    JWT_SECRET_KEY = os.environ.get("ASZDA_JWT_SECRET_KEY", "")

    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "postgresql+psycopg://aszda:aszda@localhost:5432/aszda"
    )
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", REDIS_URL)
    CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", REDIS_URL)
    # Development convenience: run jobs inside the web process instead of a worker.
    # Never enable this in production (long jobs would block web requests).
    CELERY_TASK_ALWAYS_EAGER = _bool("ASZDA_CELERY_EAGER", False)

    # Public URL of the web app; used to build links in emails.
    FRONTEND_URL = os.environ.get("ASZDA_FRONTEND_URL", "http://localhost:3000").rstrip("/")
    CORS_ORIGINS = _list("ASZDA_CORS_ORIGINS", "http://localhost:3000")

    # Auth
    ACCESS_TOKEN_TTL = timedelta(minutes=_int("ASZDA_ACCESS_TOKEN_MINUTES", 15))
    REFRESH_TOKEN_TTL = timedelta(days=_int("ASZDA_REFRESH_TOKEN_DAYS", 14))
    EMAIL_VERIFICATION_TTL = timedelta(hours=48)
    PASSWORD_RESET_TTL = timedelta(minutes=60)
    # Two browser tabs may refresh at the same moment with the same token. Reuse
    # within this many seconds is treated as that race, not as token theft.
    REFRESH_REUSE_GRACE_SECONDS = _int("ASZDA_REFRESH_REUSE_GRACE_SECONDS", 20)
    REFRESH_COOKIE_NAME = "aszda_refresh"
    REFRESH_COOKIE_PATH = "/api/auth"
    COOKIE_SECURE = _bool("ASZDA_COOKIE_SECURE", True)
    REQUIRE_VERIFIED_EMAIL_FOR_GENERATION = _bool("ASZDA_REQUIRE_VERIFIED_EMAIL", True)

    # Rate limiting (Flask-Limiter). Use Redis in production so limits are shared
    # by all application processes.
    RATELIMIT_STORAGE_URI = os.environ.get("ASZDA_RATELIMIT_STORAGE_URI", "memory://")
    RATELIMIT_DEFAULT = os.environ.get("ASZDA_RATELIMIT_DEFAULT", "300 per minute")
    RATELIMIT_HEADERS_ENABLED = True
    RATELIMIT_ENABLED = True

    # Email
    MAIL_BACKEND = os.environ.get("ASZDA_MAIL_BACKEND", "console")  # console | smtp
    MAIL_FROM = os.environ.get("ASZDA_MAIL_FROM", "ASZDA <no-reply@example.com>")
    SMTP_HOST = os.environ.get("ASZDA_SMTP_HOST", "")
    SMTP_PORT = _int("ASZDA_SMTP_PORT", 587)
    SMTP_USERNAME = os.environ.get("ASZDA_SMTP_USERNAME", "")
    SMTP_PASSWORD = os.environ.get("ASZDA_SMTP_PASSWORD", "")
    SMTP_USE_TLS = _bool("ASZDA_SMTP_USE_TLS", True)

    # Storage
    STORAGE_BACKEND = os.environ.get("ASZDA_STORAGE_BACKEND", "local")  # local | s3
    LOCAL_STORAGE_ROOT = os.environ.get(
        "ASZDA_LOCAL_STORAGE_ROOT",
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "var", "storage"),
    )
    S3_BUCKET = os.environ.get("ASZDA_S3_BUCKET", "")
    S3_REGION = os.environ.get("ASZDA_S3_REGION", "")
    S3_ENDPOINT_URL = os.environ.get("ASZDA_S3_ENDPOINT_URL", "") or None
    S3_ACCESS_KEY_ID = os.environ.get("ASZDA_S3_ACCESS_KEY_ID", "") or None
    S3_SECRET_ACCESS_KEY = os.environ.get("ASZDA_S3_SECRET_ACCESS_KEY", "") or None
    SIGNED_URL_TTL_SECONDS = _int("ASZDA_SIGNED_URL_TTL_SECONDS", 900)
    MAX_UPLOAD_MB = _int("ASZDA_MAX_UPLOAD_MB", 50)
    # Flask rejects bigger request bodies with 413 before our code runs.
    MAX_CONTENT_LENGTH = (MAX_UPLOAD_MB + 1) * 1024 * 1024

    # Credits and usage limits (see docs/CREDITS.md)
    PRICING_FILE = os.environ.get("ASZDA_PRICING_FILE", "")
    # One-time free credits, given when a new account confirms its email address (never expire).
    SIGNUP_CREDIT_GRANT = _int("ASZDA_SIGNUP_CREDIT_GRANT", 50)
    # Abuse guard: at most this many sign-up grants per UTC day across all accounts (0 = no cap).
    SIGNUP_GRANT_DAILY_CAP = _int("ASZDA_SIGNUP_GRANT_DAILY_CAP", 200)
    MAX_CREDITS_PER_JOB = _int("ASZDA_MAX_CREDITS_PER_JOB", 500)
    MAX_ACTIVE_JOBS_PER_USER = _int("ASZDA_MAX_ACTIVE_JOBS_PER_USER", 3)
    DAILY_JOB_LIMIT = _int("ASZDA_DAILY_JOB_LIMIT", 50)
    MONTHLY_CREDIT_LIMIT = _int("ASZDA_MONTHLY_CREDIT_LIMIT", 5000)

    # AI providers. Keys are read only on the server and never returned by the API.
    # See docs/PROVIDERS.md for each provider's setup.
    ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
    # Offered Claude models; the first is the default.
    ANTHROPIC_TEXT_MODELS = _list("ASZDA_ANTHROPIC_TEXT_MODELS", "claude-opus-5-5")
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
    OPENAI_TTS_MODEL = os.environ.get("ASZDA_OPENAI_TTS_MODEL", "gpt-4o-mini-tts")
    # Offered GPT Image models; ASZDA_OPENAI_IMAGE_MODEL is the default.
    OPENAI_IMAGE_MODELS = _list("ASZDA_OPENAI_IMAGE_MODELS", "gpt-image-2.5-sunburst,gpt-image-2")
    OPENAI_IMAGE_MODEL = os.environ.get("ASZDA_OPENAI_IMAGE_MODEL", "gpt-image-2.5-sunburst")
    RUNWAY_API_KEY = os.environ.get("RUNWAYML_API_SECRET", "")
    RUNWAY_VIDEO_MODEL = os.environ.get("ASZDA_RUNWAY_VIDEO_MODEL", "gen4.5")
    # Google Gemini API (Veo video). The key comes from Google AI Studio.
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
    # ...or Vertex AI instead (names the google-genai SDK itself uses). Google Cloud credentials
    # come from GOOGLE_APPLICATION_CREDENTIALS or the platform; they are never read by ASZDA.
    GOOGLE_USE_VERTEXAI = _bool("GOOGLE_GENAI_USE_VERTEXAI", False)
    GOOGLE_CLOUD_PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
    GOOGLE_CLOUD_LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "")
    # Veo models to offer. No default: check availability first (docs/PROVIDERS.md).
    GOOGLE_VIDEO_MODELS = _list("ASZDA_GOOGLE_VIDEO_MODELS", "")
    GOOGLE_VIDEO_MODEL = os.environ.get("ASZDA_GOOGLE_VIDEO_MODEL", "")

    # Which provider handles each kind of work when the user does not pick one, and which
    # others may be used instead if it is not ready (see app/services/orchestrator.py).
    AI_TEXT_PROVIDER = os.environ.get("ASZDA_AI_TEXT_PROVIDER", "anthropic")
    AI_TEXT_FALLBACKS = _list("ASZDA_AI_TEXT_FALLBACKS", "")
    AI_IMAGE_PROVIDER = os.environ.get("ASZDA_AI_IMAGE_PROVIDER", "openai")
    AI_IMAGE_FALLBACKS = _list("ASZDA_AI_IMAGE_FALLBACKS", "")
    AI_VIDEO_PROVIDER = os.environ.get("ASZDA_AI_VIDEO_PROVIDER", "runway")
    AI_VIDEO_FALLBACKS = _list("ASZDA_AI_VIDEO_FALLBACKS", "google")
    AI_VOICE_PROVIDER = os.environ.get("ASZDA_AI_VOICE_PROVIDER", "openai")
    AI_VOICE_FALLBACKS = _list("ASZDA_AI_VOICE_FALLBACKS", "")
    # Providers switched off even when their key is set (comma-separated names).
    DISABLED_PROVIDERS = _list("ASZDA_DISABLED_PROVIDERS", "")
    PROVIDER_POLL_INTERVAL_SECONDS = _int("ASZDA_PROVIDER_POLL_SECONDS", 10)
    PROVIDER_MAX_POLL_MINUTES = _int("ASZDA_PROVIDER_MAX_POLL_MINUTES", 30)
    # Stuck-job recovery: a queued job older than this is failed and refunded...
    STUCK_QUEUED_MINUTES = _int("ASZDA_STUCK_QUEUED_MINUTES", 30)
    # ...and so is a running job with no provider task after this long (a Claude call can
    # take up to 10 minutes per attempt, with retries).
    STUCK_RUNNING_MINUTES = _int("ASZDA_STUCK_RUNNING_MINUTES", 45)

    # ---- Money and payments (see docs/BILLING.md) ------------------------------
    # Prices are shown in DISPLAY_CURRENCY. REFERENCE_CURRENCY amounts are optional,
    # clearly labelled conversions using a fixed rate the founder configures. It is a
    # business reference rate, not a live market rate, and it is never used to charge.
    DISPLAY_CURRENCY = "USD"
    REFERENCE_CURRENCY = "KES"
    USD_TO_KES_REFERENCE_RATE = os.environ.get("ASZDA_USD_TO_KES_REFERENCE_RATE", "133")
    BILLING_CATALOG_FILE = os.environ.get(
        "ASZDA_BILLING_CATALOG_FILE",
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "billing_catalog.json"),
    )
    PAYSTACK_SECRET_KEY = os.environ.get("PAYSTACK_SECRET_KEY", "")
    # Paystack charges in the display currency (USD). Checkout stays OFF until the
    # founder has confirmed the Paystack account accepts and settles USD
    # (docs/BILLING.md, "Enabling USD checkout"). ASZDA never converts a charge to KES.
    PAYSTACK_USD_ENABLED = _bool("ASZDA_PAYSTACK_USD_ENABLED", False)
    # Payment processing fee assumed in admin margin reports (Paystack Kenya international
    # card rate as published on paystack.com/ke/pricing, 3.8%; check it is still current).
    PAYMENT_FEE_PERCENT = os.environ.get("ASZDA_PAYMENT_FEE_PERCENT", "3.8")

    LOG_LEVEL = os.environ.get("ASZDA_LOG_LEVEL", "INFO")

    @classmethod
    def validate(cls) -> list[str]:
        """Return a list of configuration problems (empty when fine)."""
        return []


class DevelopmentConfig(BaseConfig):
    ENV_NAME = "development"
    SECRET_KEY = BaseConfig.SECRET_KEY or "dev-only-secret-key-change-me-0000000000"
    JWT_SECRET_KEY = BaseConfig.JWT_SECRET_KEY or "dev-only-jwt-secret-change-me-000000000"
    COOKIE_SECURE = _bool("ASZDA_COOKIE_SECURE", False)


class TestingConfig(BaseConfig):
    ENV_NAME = "testing"
    TESTING = True
    SECRET_KEY = "test-secret-key-0000000000000000000000"
    JWT_SECRET_KEY = "test-jwt-secret-0000000000000000000000"
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "TEST_DATABASE_URL", "postgresql+psycopg://aszda:aszda@localhost:5432/aszda_test"
    )
    COOKIE_SECURE = False
    CELERY_TASK_ALWAYS_EAGER = True
    RATELIMIT_ENABLED = False
    MAIL_BACKEND = "memory"
    ANTHROPIC_API_KEY = ""
    OPENAI_API_KEY = ""
    RUNWAY_API_KEY = ""
    GEMINI_API_KEY = ""
    GOOGLE_USE_VERTEXAI = False
    GOOGLE_VIDEO_MODELS: list[str] = []
    PRICING_FILE = ""
    SIGNUP_CREDIT_GRANT = 0  # tests that need it switch it on
    PROVIDER_POLL_INTERVAL_SECONDS = 0
    PAYSTACK_SECRET_KEY = ""
    PAYSTACK_USD_ENABLED = False
    USD_TO_KES_REFERENCE_RATE = "133"


class ProductionConfig(BaseConfig):
    ENV_NAME = "production"

    @classmethod
    def validate(cls) -> list[str]:
        problems = []
        if len(cls.SECRET_KEY) < 32:
            problems.append("ASZDA_SECRET_KEY must be set to at least 32 random characters")
        if len(cls.JWT_SECRET_KEY) < 32:
            problems.append("ASZDA_JWT_SECRET_KEY must be set to at least 32 random characters")
        if cls.JWT_SECRET_KEY == cls.SECRET_KEY:
            problems.append("ASZDA_JWT_SECRET_KEY must differ from ASZDA_SECRET_KEY")
        if not os.environ.get("DATABASE_URL"):
            problems.append("DATABASE_URL must be set")
        if not cls.COOKIE_SECURE:
            problems.append("ASZDA_COOKIE_SECURE must be true in production (HTTPS only)")
        if cls.RATELIMIT_STORAGE_URI.startswith("memory"):
            problems.append("ASZDA_RATELIMIT_STORAGE_URI should point at Redis in production")
        if cls.MAIL_BACKEND != "smtp":
            problems.append("ASZDA_MAIL_BACKEND must be 'smtp' in production")
        if cls.PAYSTACK_SECRET_KEY.startswith("sk_test_") and not _bool("ASZDA_ALLOW_TEST_PAYMENTS", False):
            problems.append("PAYSTACK_SECRET_KEY is a test key; use the live key in production "
                            "(or set ASZDA_ALLOW_TEST_PAYMENTS=true on a staging server)")
        if cls.CELERY_TASK_ALWAYS_EAGER:
            problems.append("ASZDA_CELERY_EAGER must be off in production; run a Celery worker")
        if cls.STORAGE_BACKEND == "s3" and not cls.S3_BUCKET:
            problems.append("ASZDA_S3_BUCKET must be set when ASZDA_STORAGE_BACKEND=s3")
        return problems


CONFIGS = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}


def get_config(name: str | None = None) -> type[BaseConfig]:
    name = name or os.environ.get("ASZDA_ENV", "development")
    try:
        return CONFIGS[name]
    except KeyError as exc:
        raise RuntimeError(f"Unknown ASZDA_ENV '{name}'. Use one of: {', '.join(CONFIGS)}") from exc
