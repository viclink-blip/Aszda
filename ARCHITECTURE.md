# ASZDA Studio — Architecture

## The big picture

```
 Browser ──► Next.js web app ──(/api/* rewrite or nginx)──► Flask API ──► PostgreSQL
                                                              │   │
                                                              │   └──► Object storage (local disk / S3)
                                                              ▼
                                                    Redis (queue) ──► Celery worker ──► AI providers
                                                                                         (Anthropic, OpenAI, Runway)
```

- **Next.js web app** (`frontend/`): all screens. It never holds provider API keys and never
  decides prices or balances; it only displays what the API returns.
- **Flask API** (`backend/`): the single source of truth for users, projects, credits and jobs.
- **PostgreSQL**: all structured data. Large media files are *not* stored here.
- **Object storage**: media bytes. Local folder in development, S3-compatible bucket in production.
- **Redis + Celery**: AI generation can take minutes, so it runs in a background worker,
  not inside a web request.

## Backend layers

| Layer | Folder | Responsibility |
|---|---|---|
| Routes | `app/api/` | Parse HTTP, check auth, call services, return JSON. No business rules. |
| Schemas | `app/schemas/` | Request validation (pydantic, unknown fields rejected) and response serialization (allow-list). |
| Services | `app/services/` | Business logic: auth, projects, assets, credits, pricing, generation jobs, audit. |
| Models | `app/models/` | Database tables, constraints, indexes. |
| Providers | `app/providers/` | One adapter per AI vendor behind a common interface. |
| Storage | `app/storage/` | Save/open/delete files and create short-lived links. |
| Tasks | `app/tasks/` | Thin Celery wrappers that call the generation service. |
| Security | `app/security/` | Password hashing, tokens, auth decorators, security headers. |

## Key flows

### Sign-in and sessions
1. `POST /api/auth/login` verifies the Argon2id password hash.
2. The API creates an `AuthSession` row and returns a **15-minute access token** (JWT) in the
   JSON body plus a **refresh token** in an `HttpOnly; SameSite=Strict` cookie limited to `/api/auth`.
3. The web app keeps the access token only in memory. When it expires, it calls
   `POST /api/auth/refresh`, which **rotates** the refresh token (each one works once).
4. If an old refresh token is ever reused, the whole session is revoked (likely theft).
5. Every request re-checks that the session is still active, so sign-out is immediate.

### A generation job

```
POST /api/generation-jobs  (Idempotency-Key header)
  ├─ same key seen before?            → return that job (no double charge)
  ├─ email verified? project owned?   → else 403/404
  ├─ adapter.validate(params)         → 422 on bad settings
  ├─ provider key configured?         → else 503 provider_not_configured
  ├─ price configured?                → else 409 pricing_not_configured
  ├─ lock credit account (row lock)
  ├─ limits: per job, active jobs, daily, monthly
  ├─ insert job (status=queued) + ledger RESERVE (−estimate) in ONE transaction
  └─ enqueue Celery task
Worker:
  queued → validating → processing → provider.submit()
     ├─ synchronous provider (Claude, OpenAI TTS): result now
     └─ asynchronous provider (Runway): store task id, poll every N seconds
  completed → save outputs as Assets, charge actual usage (≤ reserved), RELEASE the rest
  failed    → REFUND the reservation (minus usage the provider says it billed)
  cancelled → provider cancel if supported, REFUND
```

Allowed status transitions are declared in `app/models/generation.py` (`TRANSITIONS`). Every
ledger entry has a unique reference like `job:<id>:refund`, so a retried task can never
apply it twice. Temporary provider errors are retried (max 3 attempts) **only if nothing
was submitted to the provider yet**, so a retry can never be billed twice by the provider.

### Provider adapters
Each adapter (`app/providers/*.py`) declares:
- its models, the **kind** each produces (text, video, speech...), and the **settings** each model
  supports (`SettingField`), which the web app renders dynamically — unsupported settings are never shown;
- a pydantic schema that validates settings;
- `estimate_usage()` — an upper bound, used to reserve credits;
- `submit()` / `poll()` / `cancel()` and error classification (retryable or not);
- the environment variable holding its credential.

Business logic never imports a vendor SDK. Adding ASZDA's own model later means writing one
more adapter.

## Data model (summary)

`users` · `user_profiles` · `auth_sessions` · `refresh_tokens` · `user_tokens` (email links) ·
`projects` · `characters` · `scenes` (+ `scene_characters`) · `assets` · `generation_jobs` ·
`credit_accounts` · `credit_transactions` · `audit_events`. Details in [docs/DATABASE.md](docs/DATABASE.md).

Tables proposed in the brief but intentionally **not created yet** (no feature uses them):
`ProjectMember` (collaboration), `Storyboard` (a project's storyboard is its ordered scenes),
`AIProviderConfiguration` (providers are configured by environment variables + pricing file),
`Subscription`, `Payment` (waiting for the payment-provider decision). Each can be added with a
migration when its feature is built.

## Design principles
- **Honesty**: no simulated generation, invented prices or fake numbers.
- **Server is the authority** for identity, ownership, balances and costs.
- **Ownership checks everywhere**: other users' objects answer 404, not 403, so IDs cannot be probed.
- **Small, replaceable parts**: providers, storage and email are behind interfaces.
- **Beginner-readable**: plain names, comments that explain *why*.
