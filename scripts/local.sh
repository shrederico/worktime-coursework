#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
python3 scripts/setup_env.py
set -a
. ./.env
set +a
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python manage.py migrate --noinput
.venv/bin/python manage.py seed_demo
.venv/bin/python manage.py collectstatic --noinput
exec .venv/bin/python manage.py runserver 127.0.0.1:8000 --noreload
