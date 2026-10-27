#!/bin/sh
# Daily PostgreSQL backup for docker-compose.prod.yml. Keeps the last 14 days in /var/backups/aszda.
# Install (as root):  crontab -e   then add:
#   30 2 * * * /root/Aszda/deploy/backup.sh >> /var/log/aszda-backup.log 2>&1
# Copy the files off the server regularly too (e.g. to your computer, or enable Droplet backups).
set -eu
cd "$(dirname "$0")/.."
mkdir -p /var/backups/aszda
file="/var/backups/aszda/aszda-$(date +%Y%m%d-%H%M).sql.gz"
docker compose -f docker-compose.prod.yml --env-file .env.production exec -T db \
  pg_dump -U aszda --no-owner aszda | gzip > "$file"
find /var/backups/aszda -name 'aszda-*.sql.gz' -mtime +14 -delete
echo "$(date) backup written: $file"
