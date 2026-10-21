# Testing

## Backend (`backend/`)

```bash
source .venv/bin/activate
pytest                          # whole suite
pytest tests/test_generation.py -k refund -v   # a subset, verbose
pytest --cov=app                # with coverage
ruff check .                    # lint
flask --app wsgi db check       # models match migrations
```

- Tests use a real PostgreSQL database (`TEST_DATABASE_URL`, default `aszda_test`). At the start of
  a run the schema is rebuilt by running all migrations down and up, so migrations are tested too.
  Every test starts from empty tables.
- Celery runs in eager mode, so jobs finish inside the test.
- **No paid API is ever called.** `tests/fakes.py` provides a fake synchronous text provider and a
  fake asynchronous video provider; the real adapters are tested with mocked HTTP/SDK calls in
  `tests/test_providers.py`.

| File | Covers |
|---|---|
| `test_auth.py` | registration, login, invalid credentials, protected routes, refresh rotation and reuse detection, CSRF header, logout, expired tokens/sessions, email verification, password reset and change, deactivation, account deletion |
| `test_projects.py` | project CRUD, validation, search, cross-user isolation, characters, scenes, reordering, duplication, dashboard |
| `test_assets.py` | content-based type detection, disguised files, size limit, path traversal, signed links, cross-user isolation, deletion |
| `test_generation.py` | job success and credit reconciliation, invalid requests, unconfigured/unpriced providers, insufficient credits, unverified email, idempotency, retries, refunds, refusals, async polling, cancellation, limits, cross-user isolation, quotes, catalog never leaks keys |
| `test_admin_security.py` | admin-only access, credit grants with audit, self-lockout guard, role change revocation, key secrecy, security headers, error leakage, login rate limit, OpenAPI, health |
| `test_providers.py` | Anthropic/OpenAI/Runway request shapes, validation, error classification, polling, cancel, HTTPS-only downloads |

`test_billing.py` covers currency conversion and formatting, catalog validation, price-manipulation rejection, verification of amount/currency/plan, idempotent credit grants, webhook signatures, duplicates and retries, and the subscription lifecycle (Paystack mocked).

Frontend money formatting: `cd frontend && npm test`.

## Frontend (`frontend/`)

```bash
npm run lint
npx tsc --noEmit
npm run build
```

## Continuous integration
`.github/workflows/ci.yml` runs all of the above on every push to `main` and on pull requests,
with PostgreSQL as a service container.
