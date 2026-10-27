# Deploying ASZDA Studio on DigitalOcean

Everything runs on **one Droplet** with Docker, as on your laptop, plus **DigitalOcean Spaces** for
media files. Caddy gets the HTTPS certificate automatically.

```
Internet ──► Caddy (HTTPS, ports 80/443)
               ├── /api/*  ──► API (Flask)  ──► PostgreSQL, Redis, Spaces, AI providers
               └── the rest ──► Web app (Next.js)
             Worker (Celery + scheduler) ──► runs the generations in the background
```

Files used: `docker-compose.prod.yml`, `deploy/Caddyfile`, `.env.production.example`,
`deploy/backup.sh`.

## 1. What to create in DigitalOcean (≈ 15 minutes)

| What | Where | Recommended |
|---|---|---|
| **Droplet** | Create → Droplets | Ubuntu 24.04 LTS, **4 GB RAM / 2 CPUs** (building the web app needs the memory). Choose the region closest to your users (e.g. Frankfurt `fra1` or London `lon1` for Kenya). Add your SSH key. Tick **Backups** if you can afford it. |
| **Spaces bucket** | Create → Spaces Object Storage | Same region. Name e.g. `aszda-media`. **Restrict file listing** / keep it private; no CDN needed. |
| **Spaces access key** | Spaces Object Storage → Access Keys | Create a key limited to that bucket (read/write). Copy the key and secret: the secret is shown once. |
| **Domain** | Your domain registrar, or Networking → Domains | An **A record** for your domain (e.g. `studio.yourdomain.com`) pointing to the Droplet's IP. Optionally `www.` too. |
| **Firewall** | Networking → Firewalls | Allow inbound **22** (SSH), **80** and **443** only. |

You also need an **SMTP email service** (Brevo, Mailgun, Postmark, Amazon SES...): production
mode refuses to start without real email, because sign-up and password reset send emails.

## 2. Prepare the server

```bash
ssh root@YOUR_DROPLET_IP

# Docker (official install script) and git
curl -fsSL https://get.docker.com | sh
apt-get install -y git

# Code
git clone https://github.com/viclink-blip/Aszda.git
cd Aszda
```

If the repository is private, use a GitHub personal access token or a deploy key when cloning.

## 3. Settings

```bash
cp .env.production.example .env.production
nano .env.production
```

Fill in every value. Comments must stay on their own lines. Create the three secrets with
`openssl rand -base64 48` (run it three times, use each result once).

Key values:
- `ASZDA_DOMAIN=studio.yourdomain.com` (no https://)
- `ASZDA_FRONTEND_URL=https://studio.yourdomain.com` and the same in `ASZDA_CORS_ORIGINS`
- `ASZDA_S3_ENDPOINT_URL=https://fra1.digitaloceanspaces.com` (your region), `ASZDA_S3_REGION=fra1`
- your SMTP details, your AI provider keys

Then protect the file: `chmod 600 .env.production`.

## 4. Start

```bash
DC="docker compose -f docker-compose.prod.yml --env-file .env.production"
$DC up -d --build
$DC exec api flask --app wsgi db upgrade
$DC exec api flask --app wsgi aszda create-admin
$DC exec api flask --app wsgi aszda pricing-apply pricing.approved.json --yes
$DC exec api flask --app wsgi aszda providers-test
```

Open `https://studio.yourdomain.com`. The first visit can take a minute while Caddy gets the
certificate. If the API refuses to start, `$DC logs api` lists exactly which setting is missing.

## 5. Updating to a new version

```bash
cd ~/Aszda
git pull
DC="docker compose -f docker-compose.prod.yml --env-file .env.production"
./deploy/backup.sh
$DC up -d --build
$DC exec api flask --app wsgi db upgrade
```

## 6. Backups

- `deploy/backup.sh` writes a compressed database dump to `/var/backups/aszda` and keeps 14 days.
  Schedule it daily with `crontab -e` (the line is in the script). Also copy dumps off the server
  regularly, or enable Droplet Backups.
- Media files are in Spaces, which DigitalOcean stores redundantly; deleting a file in ASZDA
  deletes it there too.
- For a bigger launch, consider a **DigitalOcean Managed PostgreSQL** database (automatic backups
  and failover): set `DATABASE_URL` in `.env.production` to its connection string and remove the
  `db` service.

## 7. Useful commands

```bash
DC="docker compose -f docker-compose.prod.yml --env-file .env.production"
$DC ps                      # what is running
$DC logs -f --tail=100 api  # API log (also: worker, web, caddy)
$DC restart worker          # after changing .env.production: use  $DC up -d --force-recreate api worker
```

## Not covered yet

- **Payments** stay off (`ASZDA_PAYSTACK_USD_ENABLED=false`) until Paystack confirms USD and checkout
  has been tested. The Paystack webhook URL will be `https://studio.yourdomain.com/api/billing/paystack/webhook`.
- Error monitoring (e.g. Sentry) and uptime alerts on `https://studio.yourdomain.com/api/health/ready`.
- This setup has **not been run on a real Droplet yet**; the files were checked, but the first
  deployment is the real test.
