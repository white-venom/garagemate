#!/usr/bin/env bash
# Pull the latest code and restart. Run on the server as the ubuntu user.
set -euo pipefail

cd /home/ubuntu/garagemate
git pull --ff-only

cd backend
.venv/bin/pip install -r requirements.txt
.venv/bin/python manage.py migrate --noinput
.venv/bin/python manage.py collectstatic --noinput
sudo systemctl restart garagemate

echo "Deployed $(git rev-parse --short HEAD)"
