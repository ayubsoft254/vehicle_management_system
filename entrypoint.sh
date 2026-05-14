#!/bin/sh

set -eu

log() {
  echo "[entrypoint] $*"
}

is_true() {
  case "${1:-}" in
    1|true|TRUE|yes|YES|on|ON) return 0 ;;
    *) return 1 ;;
  esac
}

wait_for_service() {
  host="$1"
  port="$2"
  name="$3"

  log "Waiting for $name at ${host}:${port}..."
  i=0
  until nc -z "$host" "$port" >/dev/null 2>&1; do
    i=$((i + 1))
    if [ "$i" -ge 120 ]; then
      log "Timed out waiting for $name"
      exit 1
    fi
    sleep 1
  done
  log "$name is ready"
}

mkdir -p /app/logs /app/static_collected /app/media

if is_true "${WAIT_FOR_DB:-true}"; then
  wait_for_service "${DB_HOST:-db}" "${DB_PORT:-5432}" "database"
fi

if is_true "${WAIT_FOR_REDIS:-false}"; then
  wait_for_service "${REDIS_HOST:-redis}" "${REDIS_PORT:-6379}" "redis"
fi

if is_true "${RUN_MIGRATIONS:-false}"; then
  log "Running database migrations..."
  python manage.py migrate --noinput
fi

if is_true "${COLLECT_STATIC:-false}"; then
  log "Collecting static files..."
  python manage.py collectstatic --noinput
fi

if is_true "${CREATE_CACHE_TABLE:-false}"; then
  python manage.py createcachetable >/dev/null 2>&1 || true
fi

log "Starting: $*"
exec "$@"
