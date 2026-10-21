# ASZDA Studio

**Imagine It. Create It.**

ASZDA Studio is an AI creative workspace from ASZDA. People describe an idea and turn it
into a production: story and script, characters, a storyboard of scenes, video clips,
voice-over, and (later) a finished film.

ASZDA does not train its own foundation models today. It connects to leading AI
providers through a provider-independent layer, so providers can be swapped and ASZDA's
own models can be added later without rewriting the app.

> **Status:** first build milestone (foundation). See [What works today](#what-works-today)
> and [ROADMAP.md](ROADMAP.md).

---

## What works today

| Area | Status |
|---|---|
| Accounts: sign up, sign in, email verification, password reset, sign out everywhere, account deletion | Implemented and tested |
| Projects, characters, storyboard scenes (create, edit, reorder, duplicate, delete) | Implemented and tested |
| Media uploads (images, video, audio) with type detection, size limits, private storage, short-lived links | Implemented and tested |
| Background generation jobs (queue, progress, cancel, retry, idempotency) | Implemented and tested (with fake providers + one real queue run) |
| Credits ledger: reserve → release/refund, usage limits | Implemented and tested |
| Admin API: users, credits, jobs, usage, providers, audit log | Implemented and tested |
| Script/story writing with **Anthropic Claude** | Implemented; needs `ANTHROPIC_API_KEY` + a configured price |
| Voice (text-to-speech) with **OpenAI** | Implemented; needs `OPENAI_API_KEY` + a configured price |
| Video (text/image-to-video) with **Runway** (`gen4.5`, `veo3.1_fast`) | Implemented; needs `RUNWAYML_API_SECRET` + a configured price |
| Image generation, AI Film Director, final video assembly/export, payments | **Not implemented yet** (planned) |

Nothing in the app pretends to generate: a model is usable only when its API key **and**
its credit price are configured. Otherwise the app shows it as unavailable.

---

## Repository layout

```
aszda/
├── backend/            Flask API, database models, AI providers, background jobs (Python)
│   ├── app/
│   │   ├── api/        HTTP routes (one file per area)
│   │   ├── models/     Database tables (SQLAlchemy)
│   │   ├── services/   Business logic (auth, projects, credits, generation...)
│   │   ├── providers/  AI provider adapters (Anthropic, OpenAI, Runway)
│   │   ├── storage/    Local / S3 file storage
│   │   ├── security/   Passwords, tokens, auth decorators, headers
│   │   └── tasks/      Celery background tasks
│   ├── migrations/     Alembic database migrations
│   └── tests/          pytest test suite
├── frontend/           Next.js web app (TypeScript, Tailwind)
├── deploy/             Production examples (nginx)
├── docs/               Detailed documentation
├── docker-compose.yml  One-command local stack
└── .env.example        All settings with placeholder values
```

---

## Quick start (local, without Docker)

You need: **Python 3.12+**, **Node.js 22+**, **PostgreSQL 16**, **Redis 7**.

### 1. Database (once)

```bash
# In any terminal. Creates a database user and two databases (app + tests).
sudo -u postgres psql -c "CREATE ROLE aszda LOGIN PASSWORD 'aszda' CREATEDB;"
sudo -u postgres createdb -O aszda aszda
sudo -u postgres createdb -O aszda aszda_test
```

### 2. Backend (in `backend/`)

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp ../.env.example .env              # then edit .env (see docs/ENVIRONMENT.md)
flask --app wsgi db upgrade          # create the tables
flask --app wsgi aszda create-admin  # first admin (asks for email, name, password; or --email/--name)
flask --app wsgi run --port 5000     # API at http://localhost:5000/api/health
```

In a **second terminal** (also in `backend/`, with the venv activated), start the worker
that runs generation jobs:

```bash
celery -A celery_worker.celery worker --loglevel=info -Q aszda
```

(For quick experiments you can skip the worker by setting `ASZDA_CELERY_EAGER=true`
in `.env`; jobs then run inside the API process. Never do this in production.)

### 3. Frontend (in `frontend/`)

```bash
cd frontend
npm install
cp .env.example .env.local           # ASZDA_API_URL=http://localhost:5000
npm run dev                          # http://localhost:3000
```

### 4. Turn on an AI provider

1. Put the key in `backend/.env`, e.g. `ANTHROPIC_API_KEY=...`
2. Copy `backend/pricing.example.json` to `backend/pricing.json`, set the credit prices
   you want, and set `ASZDA_PRICING_FILE=./pricing.json`.
3. Restart the API and worker. Check with `flask --app wsgi aszda check-pricing`.
4. Give yourself credits: `flask --app wsgi aszda grant-credits you@example.com 500 --reason "testing"`.

See [docs/PROVIDERS.md](docs/PROVIDERS.md) and [docs/CREDITS.md](docs/CREDITS.md).

## Quick start (Docker)

You need Docker with the **Compose** plugin (`docker compose version` should print a version).
On Ubuntu, if it says `unknown flag` or `'compose' is not a docker command`:
`sudo apt install docker-compose-v2` (Docker from Ubuntu's own packages) or
`sudo apt install docker-compose-plugin` (Docker from docker.com's repository).

```bash
cp .env.example .env                                  # in the project root; edit values
docker compose up --build
docker compose exec api flask --app wsgi db upgrade
docker compose exec api flask --app wsgi aszda create-admin
```

## Running the tests

```bash
cd backend && source .venv/bin/activate
pytest                       # 72 tests, uses the aszda_test database, no paid API calls
ruff check .                 # lint
flask --app wsgi db check    # models and migrations agree

cd ../frontend
npm run lint && npx tsc --noEmit && npm run build
```

More in [docs/TESTING.md](docs/TESTING.md).

---

## Screenshots

From the first build's browser smoke test: [docs/screenshots/](docs/screenshots/)
(home, sign-up, dashboard light/dark, storyboard, studios, mobile, admin, settings).

## Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) — how the pieces fit together, and why
- [ROADMAP.md](ROADMAP.md) — phases and what comes next
- [SECURITY.md](SECURITY.md) — security model and reporting
- [docs/API.md](docs/API.md) — API overview (full spec at `GET /api/openapi.json`)
- [docs/ENVIRONMENT.md](docs/ENVIRONMENT.md) — every setting explained
- [docs/DATABASE.md](docs/DATABASE.md) — tables and migrations
- [docs/PROVIDERS.md](docs/PROVIDERS.md) — AI providers: what is verified, how to add one
- [docs/CREDITS.md](docs/CREDITS.md) — credits, pricing and limits
- [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) — going to production
- [docs/TESTING.md](docs/TESTING.md) — test strategy and commands
- [docs/DATA_RETENTION.md](docs/DATA_RETENTION.md) — what we store and how deletion works
- [docs/DECISIONS.md](docs/DECISIONS.md) — technology and version choices
