#!/bin/bash
# Entrypoint script for Django container

set -e

echo "Starting Vehicle Management System..."

# Wait for database to be ready
echo "Waiting for database..."
while ! nc -z db 5432; do
  sleep 0.1
done
echo "Database is ready!"

# Ensure directories have correct permissions
echo "Setting up directories..."
mkdir -p /app/logs /app/static_collected /app/media

# Run migrations
echo "Running database migrations..."
python manage.py migrate --noinput

# Collect static files (without --clear to avoid permission issues)
echo "Collecting static files..."
python manage.py collectstatic --noinput

# Create cache table (if needed)
python manage.py createcachetable 2>/dev/null || true

echo "Starting Gunicorn..."
exec gunicorn config.wsgi:application \
    --bind 0.0.0.0:3333 \
    --workers "${GUNICORN_WORKERS:-4}" \
    --threads "${GUNICORN_THREADS:-2}" \
    --timeout "${GUNICORN_TIMEOUT:-120}" \
    --access-logfile - \
    --error-logfile - \
    --log-level "${GUNICORN_LOG_LEVEL:-info}" \
    --max-requests "${GUNICORN_MAX_REQUESTS:-1000}" \
    --max-requests-jitter "${GUNICORN_MAX_REQUESTS_JITTER:-50}"
