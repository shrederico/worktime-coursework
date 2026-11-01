#!/bin/bash
# Проверка копии в отдельной временной базе. Рабочая база не изменяется.
set -euo pipefail
cd "$(dirname "$0")/.."
file=${1:?Укажите SQL-файл из backups}
test -s "$file"
check_db="worktime_restore_$(date +%Y%m%d%H%M%S)_$$"
cleanup() {
  docker compose exec -T db sh -c 'dropdb --if-exists -U "$POSTGRES_USER" "$1"' sh "$check_db"
}
trap cleanup EXIT
docker compose exec -T db sh -c 'createdb -U "$POSTGRES_USER" "$1"' sh "$check_db"
docker compose exec -T db sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$1"' sh "$check_db" < "$file" > /dev/null
docker compose exec -T db sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$1" -c "SELECT COUNT(*) AS tasks FROM tracker_task; SELECT COUNT(*) AS entries, COALESCE(SUM(hours),0) AS hours FROM tracker_timeentry;"' sh "$check_db"
printf 'Копия восстановлена в отдельную базу; рабочие данные не изменены.\n'
