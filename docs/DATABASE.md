# Database

PostgreSQL 16, accessed with SQLAlchemy 2. Schema changes are **only** made through Alembic
migrations (`backend/migrations/`); the app never creates tables at startup.

## Tables

| Table | Purpose | Notable constraints |
|---|---|---|
| `users` | Accounts | unique email; `email = lower(email)`; role enum `user/admin` |
| `user_profiles` | Display name, language, country | 1:1 with users, cascade delete |
| `auth_sessions` | One row per signed-in device | revocation reason and time |
| `refresh_tokens` | SHA-256 hashes of single-use refresh tokens | unique hash; `used_at` for reuse detection |
| `user_tokens` | Email verification / password reset tokens (hashed) | unique hash, expiry, single use |
| `projects` | A creative project | owner FK; index (owner, updated_at); `brief` JSONB |
| `characters` | Characters in a project | `traits` JSONB; optional reference image |
| `scenes` | Storyboard scenes | unique (project, position), **deferrable** so reordering works in one transaction |
| `scene_characters` | Which characters appear in which scene | composite PK |
| `assets` | Metadata for media files (bytes live in storage) | unique storage key; size ≥ 0; SHA-256 |
| `generation_jobs` | AI jobs | unique (user, idempotency key); charged ≤ reserved; progress 0–100 |
| `credit_accounts` | Balance per user | unique user; balance ≥ 0 |
| `credit_transactions` | Ledger: every balance change | unique `reference`; amount ≠ 0; balance_after ≥ 0 |
| `audit_events` | Security and admin log | indexes by time, actor, action |

IDs are random UUIDs. All timestamps are timezone-aware (UTC).

## Common commands (run in `backend/` with the venv active)

```bash
flask --app wsgi db upgrade                 # apply all migrations
flask --app wsgi db current                 # which migration the database is on
flask --app wsgi db check                   # fails if models changed without a migration
flask --app wsgi db migrate -m "add X"      # create a new migration after changing models
flask --app wsgi db downgrade               # undo the last migration (development only!)
```

## Making a schema change
1. Edit the model in `app/models/`.
2. `flask --app wsgi db migrate -m "describe the change"`.
3. **Read the generated file** in `migrations/versions/`. Autogenerate misses some things
   (for example, it does not drop PostgreSQL enum types and does not add `use_alter` foreign keys
   — see the initial migration for both).
4. `flask --app wsgi db upgrade`, run `pytest`, commit the model and the migration together.

Never edit a migration that has already run in production; write a new one. Destructive changes
(dropping columns or tables) need a backup and an explicit decision.

## Backups (production)
Use your database host's automatic daily backups with point-in-time recovery, and test a restore
before launch. Media in object storage needs its own backup/versioning policy.
