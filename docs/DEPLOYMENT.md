# Deployment

Nothing has been deployed yet. This is the recommended path for a first staging/production setup.

## What you need
| Piece | Options |
|---|---|
| A Linux server or container platform | A VPS (Hetzner, DigitalOcean, AWS Lightsail...) with Docker, or a platform such as Render/Fly.io/Railway |
| PostgreSQL 16 | Managed database with daily backups (recommended) |
| Redis 7 | Managed Redis or a container |
| Object storage | AWS S3 or S3-compatible (Cloudflare R2, Wasabi, MinIO); a **private** bucket |
| Email (SMTP) | Amazon SES, Postmark, Mailgun, Brevo... with SPF/DKIM on your domain |
| Domain + HTTPS | nginx + Let's Encrypt (see `deploy/nginx.conf.example`) or the platform's TLS |

## Processes to run
1. **API**: `gunicorn --bind 0.0.0.0:5000 --workers 3 --timeout 120 wsgi:app` (the Docker image default).
2. **Worker**: `celery -A celery_worker.celery worker --loglevel=info -Q aszda --concurrency=2`.
   Scale workers for more parallel generations.
3. **Web**: `npm run build && npm start` in `frontend/` (port 3000), with `ASZDA_API_URL` pointing at the API.
4. **Reverse proxy**: `/api/` → API **directly**, everything else → web, HTTPS only.
   Important: in production, do not send API traffic through the Next.js `/api` rewrite. That rewrite
   does not add the client IP (verified during the build), so the API would see every user as the
   Next.js server and per-IP rate limits would be shared by everyone. nginx (with
   `ASZDA_TRUSTED_PROXIES=1`) passes the real client IP. The rewrite is a development convenience.

## Production settings (minimum)
```
ASZDA_ENV=production
ASZDA_SECRET_KEY=<random 48+ chars>
ASZDA_JWT_SECRET_KEY=<different random 48+ chars>
DATABASE_URL=postgresql+psycopg://...
REDIS_URL=redis://...
ASZDA_RATELIMIT_STORAGE_URI=redis://.../1
ASZDA_COOKIE_SECURE=true
ASZDA_TRUSTED_PROXIES=1
ASZDA_FRONTEND_URL=https://studio.your-domain
ASZDA_MAIL_BACKEND=smtp  (+ SMTP settings)
ASZDA_STORAGE_BACKEND=s3 (+ S3 settings)
ASZDA_PRICING_FILE=/etc/aszda/pricing.json
```
The API **refuses to start** in production if secrets are weak, cookies are not secure, rate limits
are in memory, email is console-only, or jobs are eager.

## Release steps
1. Back up the database.
2. Deploy the new code/image.
3. `flask --app wsgi db upgrade` (once, before starting new API/worker processes).
4. Restart API and worker; check `GET /api/health/ready`.
5. First time only: `flask --app wsgi aszda create-admin`.

## Operations
- **Monitoring**: poll `/api/health/ready`; alert on 5xx rates and on jobs stuck in `processing`
  (admin → Jobs). Add an error tracker (e.g. Sentry) before launch.
- **Storage hygiene**: S3 lifecycle rules for incomplete multipart uploads; for local storage run
  `flask --app wsgi aszda cleanup-storage --dry-run` (then `--delete`).
- **Secrets**: keep them in the platform's secret store, rotate provider keys if leaked; rotating
  `ASZDA_JWT_SECRET_KEY` signs everyone out.

## Docker
`backend/Dockerfile` builds one image for API and worker (non-root user). `docker-compose.yml` is a
**development** stack. The compose file was validated with `docker compose config`; the images were
not built in the original build environment because Docker could not run there — build and test
them once on a machine with Docker.
