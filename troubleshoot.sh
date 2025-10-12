#!/bin/bash
# Quick deployment troubleshooter

echo "=== Checking Docker Containers ==="
docker-compose ps

echo ""
echo "=== Web Container Logs (last 100 lines) ==="
docker-compose logs --tail=100 web

echo ""
echo "=== Database Container Logs (last 50 lines) ==="
docker-compose logs --tail=50 db

echo ""
echo "=== Redis Container Logs (last 20 lines) ==="
docker-compose logs --tail=20 redis

echo ""
echo "=== Celery Worker Logs (last 50 lines) ==="
docker-compose logs --tail=50 celery_worker

echo ""
echo "=== Container Stats ==="
docker stats --no-stream
