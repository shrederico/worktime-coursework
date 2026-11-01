#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
python3 scripts/setup_env.py
docker compose build app
docker compose up -d db
docker compose run --rm app python manage.py migrate --noinput
docker compose run --rm app python manage.py seed_demo
docker compose up -d --wait
printf '\nПлатформа: http://localhost:8080\nGrafana: http://localhost:3000\nПароли находятся в .env (DEMO_PASSWORD и GRAFANA_PASSWORD).\n'
