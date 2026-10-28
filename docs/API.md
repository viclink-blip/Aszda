# API overview

Base path: `/api`. JSON in, JSON out. The complete machine-readable spec is served at
**`GET /api/openapi.json`** (OpenAPI 3.1) — import it into Postman, Insomnia or Swagger Editor.

## Conventions
- **Auth**: `Authorization: Bearer <access_token>` (from sign-in / refresh).
- **Errors**: `{"error": {"code": "...", "message": "...", "details": {...}}}`.
  Validation errors are `422` with `details.fields = [{field, message}]`.
- **Lists**: `?limit=` (max 100) and `?offset=`; responses are `{items, total, limit, offset}`.
- **Other users' objects** return `404`.
- **Idempotency**: `POST /generation-jobs` and `/retry` require an `Idempotency-Key` header
  (8–128 chars). Sending the same key again returns the same job (`200`) instead of creating
  and charging a new one; reusing a key for a different request returns `409`.

## Endpoints

| Method & path | What it does |
|---|---|
| `GET /health`, `GET /health/ready` | Liveness / readiness (database + queue) |
| `POST /auth/register` | Create account, sign in, send verification email |
| `POST /auth/login` | Sign in |
| `POST /auth/refresh` | New access token from the refresh cookie (needs `X-Requested-With: aszda`) |
| `POST /auth/logout` · `POST /auth/logout-all` | Sign out this device / everywhere |
| `POST /auth/verify-email` · `POST /auth/resend-verification` | Email verification |
| `POST /auth/password-reset/request` · `/confirm` | Password reset |
| `GET /auth/session` | Current user + session ID |
| `GET/PATCH/DELETE /me` | My account (delete needs password + `"confirm": "DELETE"`) |
| `POST /me/password` | Change password (signs out other devices) |
| `GET /me/credits` · `GET /me/dashboard` | Balance + ledger · dashboard summary |
| `GET/POST /projects` | List (search `q`, `status`) / create |
| `GET/PATCH/DELETE /projects/{id}` | Project with characters and scenes / update / delete |
| `POST /projects/{id}/duplicate` | Copy text, characters and scenes |
| `POST /projects/{id}/characters` · `PATCH/DELETE .../characters/{cid}` | Characters |
| `POST /projects/{id}/scenes` · `PATCH/DELETE .../scenes/{sid}` · `PUT .../scenes/order` | Storyboard |
| `GET/POST /projects/{id}/assets` | List / upload (multipart field `file`) |
| `GET /projects/{id}/jobs` | Jobs of a project |
| `GET/POST /assets` · `GET/PATCH/DELETE /assets/{id}` | All my assets |
| `GET /assets/{id}/url` | Short-lived view/download link |
| `GET /files/{signed-token}` | Serves a file (local storage), no login needed, link expires |
| `GET /providers` | Providers, models, settings, availability (never keys) |
| `POST /generation-jobs/quote` | Validate + estimate credits without running |
| `POST /generation-jobs` · `GET /generation-jobs` · `GET /generation-jobs/{id}` | Start / list / status |
| `POST /generation-jobs/{id}/cancel` · `/retry` | Cancel (refund) / retry as a new job |
| `POST /projects/{id}/director/plan` · `/apply` · `/scenes/{scene}/generate` | AI Film Director, step by step: plan, add the plan to the project, make one scene's image/video/voice |
| `POST /projects/{id}/director/films` | **Make my film**: plan, then every scene's image, video and voice, joined into one MP4. With `"from_scenes": true`: use the project's existing scenes (no new plan) and reuse what they already have (needs `Idempotency-Key`) |
| `GET /projects/{id}/director/films/current` | The project's latest film and its progress |
| `POST /projects/{id}/director/films/{film}/continue` · `/cancel` | Continue a film that waited for credits · stop starting new steps |
| `GET /admin/overview`, `/admin/users`, `/admin/jobs`, `/admin/usage`, `/admin/providers`, `/admin/audit-events`, `/admin/credit-transactions` | Admin views |
| `PATCH /admin/users/{id}` · `POST /admin/users/{id}/credits` · `GET /admin/users/{id}/credits` | Admin actions (audited) |

## Example: start a script job with curl

```bash
TOKEN=$(curl -s localhost:5000/api/auth/login -H 'Content-Type: application/json' \
  -d '{"email":"you@example.com","password":"..."}' | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

curl -s localhost:5000/api/generation-jobs \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -H "Idempotency-Key: $(python3 -c 'import uuid;print(uuid.uuid4())')" \
  -d '{"provider":"anthropic","model":"claude-opus-5-5","kind":"text",
       "params":{"task":"story_concept","prompt":"A fox in Nairobi opens a shoe shop"}}'

curl -s localhost:5000/api/generation-jobs/<job-id> -H "Authorization: Bearer $TOKEN"
```

Job `status` values: `queued → validating → processing → completed | failed | cancelled`.
