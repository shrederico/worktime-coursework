#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
mkdir -p backups
umask 077
target="backups/worktime-$(date +%Y%m%d-%H%M%S).sql"
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' > "$target.tmp"
mv "$target.tmp" "$target"
printf 'Резервная копия: %s\n' "$target"
