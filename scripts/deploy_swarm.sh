#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
: "${APP_IMAGE:?Задайте APP_IMAGE: образ из реестра с уникальным тегом версии}"
set -a
. ./.env
set +a
CONFIG_VERSION=$(python3 scripts/config_version.py)
export CONFIG_VERSION
# Первый запуск: создаём стек, затем таблицы. При обновлениях миграции должны
# оставаться совместимыми с предыдущей версией приложения.
docker stack deploy --with-registry-auth -c infra/swarm/stack.yml worktime
attempt=0
until docker run --rm --network worktime_data --env-file .env -e DB_HOST=db "$APP_IMAGE" python manage.py migrate --noinput; do
  attempt=$((attempt + 1))
  if [ "$attempt" -ge 12 ]; then exit 1; fi
  sleep 5
done
docker run --rm --network worktime_data --env-file .env -e DB_HOST=db "$APP_IMAGE" python manage.py seed_demo
python3 scripts/wait_swarm.py
attempt=0
until curl --fail --silent http://127.0.0.1:8080/health/; do
  attempt=$((attempt + 1))
  if [ "$attempt" -ge 24 ]; then exit 1; fi
  sleep 5
done
docker stack services worktime
