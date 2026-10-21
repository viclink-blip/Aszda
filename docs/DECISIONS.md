# Technology decisions

## Repository
ASZDA lives in its own repository (`viclink-blip/Aszda`), separate from the founder's other projects,
so it has an independent identity, history and deployment.

## Environment at build time (2026-10-21)
Ubuntu 24.04, Python 3.13.16, Node 22.22, npm 10.9, PostgreSQL 16.15, Redis 7.

## Backend versions (pinned in `backend/requirements.txt`)
| Package | Version | Why |
|---|---|---|
| Flask | 3.1.3 | Requested stack; application factory + blueprints |
| SQLAlchemy / Flask-SQLAlchemy | 2.1.5 / 3.1.1 | Typed ORM, row locks |
| Alembic / Flask-Migrate | 1.20.0 / 4.1.0 | Migrations |
| psycopg (binary) | 3.3.6 | Modern PostgreSQL driver |
| pydantic | 2.14.1 | Request validation and JSON schemas for OpenAPI |
| argon2-cffi | 25.1.0 | Argon2id password hashing |
| PyJWT | 2.15.1 | Access tokens (small, explicit; refresh rotation implemented in our code) |
| Flask-Limiter | 4.1.1 | Rate limiting (Redis in production) |
| flask-cors | 6.0.5 | Restricted CORS |
| Celery / redis | 5.6.3 / 8.1.0 | Background jobs |
| anthropic | 1.17.0 | Official Claude SDK |
| httpx | 0.28.1 | HTTP for OpenAI and Runway (small surface; no extra SDKs) |
| boto3 | 1.43.116 | S3-compatible storage |
| gunicorn | 26.2.0 | Production WSGI server |

Choices worth knowing:
- **pydantic instead of marshmallow**: one library validates input *and* generates the OpenAPI schemas.
- **Hand-built OpenAPI generator** (`app/api/openapi.py`, ~90 lines) instead of a framework plugin,
  to stay on plain Flask.
- **JWT + rotating opaque refresh tokens** instead of server-side sessions: works across the
  Next.js proxy, sign-out is still immediate because each request checks the session row.
- **File type detection by magic bytes** (`app/storage/sniff.py`) instead of `python-magic`, avoiding
  a system library dependency.
- **Pricing in a JSON file** rather than an admin screen: prices are a deliberate business decision,
  reviewed and versioned; an admin editor can come later.
- **No `AIProviderConfiguration` table**: keys belong in the environment/secret store, not the database.

## Frontend
See `frontend/README.md` for the exact versions selected.
