#!/usr/bin/env bash
# First time setup on a fresh Ubuntu 24.04 EC2 instance (t2.micro / t3.micro).
#
#   git clone https://github.com/white-venom/garagemate.git /home/ubuntu/garagemate
#   cp /home/ubuntu/garagemate/backend/.env.example /home/ubuntu/garagemate/backend/.env   # and edit it
#   sudo bash /home/ubuntu/garagemate/backend/deploy/setup_ec2.sh api.example.com you@example.com
#
# No domain? <elastic-ip>.sslip.io works fine, e.g. 13-233-10-20.sslip.io
set -euo pipefail

DOMAIN="${1:?usage: setup_ec2.sh <domain> <email for lets encrypt>}"
EMAIL="${2:?usage: setup_ec2.sh <domain> <email for lets encrypt>}"
APP_USER=ubuntu
BACKEND_DIR=/home/ubuntu/garagemate/backend
MEDIA_DIR=/var/www/garagemate/media

if [ ! -f "$BACKEND_DIR/.env" ]; then
    echo "Create $BACKEND_DIR/.env first (see .env.example)"
    exit 1
fi

apt-get update
apt-get install -y python3-venv python3-pip nginx certbot python3-certbot-nginx

# pip runs out of memory on 1 GB instances sometimes, a small swap file fixes that
if [ ! -f /swapfile ]; then
    fallocate -l 1G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    echo "/swapfile none swap sw 0 0" >> /etc/fstab
fi

# uploads live outside the home dir so nginx can read them
mkdir -p "$MEDIA_DIR"
chown -R "$APP_USER":www-data /var/www/garagemate
chmod -R 775 /var/www/garagemate

sudo -u "$APP_USER" bash -c "
    cd $BACKEND_DIR
    python3 -m venv .venv
    .venv/bin/pip install --upgrade pip
    .venv/bin/pip install -r requirements.txt
    .venv/bin/python manage.py migrate --noinput
    .venv/bin/python manage.py collectstatic --noinput
"

cp "$BACKEND_DIR/deploy/garagemate.service" /etc/systemd/system/garagemate.service
systemctl daemon-reload
systemctl enable --now garagemate

sed "s/DOMAIN_NAME/$DOMAIN/g" "$BACKEND_DIR/deploy/nginx.conf" > /etc/nginx/sites-available/garagemate
ln -sf /etc/nginx/sites-available/garagemate /etc/nginx/sites-enabled/garagemate
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl reload nginx

certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos -m "$EMAIL" --redirect

# once a day: clean up uploads that were never sent, and API logs older than a week
CRON_LINE="30 3 * * * cd $BACKEND_DIR && .venv/bin/python manage.py cleanup_uploads >> /tmp/cleanup_uploads.log 2>&1"
LOGS_LINE="45 3 * * * cd $BACKEND_DIR && .venv/bin/python manage.py prune_logs >> /tmp/prune_logs.log 2>&1"
( crontab -u "$APP_USER" -l 2>/dev/null | grep -v -e cleanup_uploads -e prune_logs; echo "$CRON_LINE"; echo "$LOGS_LINE" ) | crontab -u "$APP_USER" -

echo
echo "Done. Check https://$DOMAIN/api/health/"
