#!/bin/bash
# ============================================================
#  STOP DEV - Kills all host processes and stops Docker infra
# ============================================================

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Stopping host processes..."
pkill -f "uvicorn main:app" 2>/dev/null
pkill -f "celery -A celery_worker" 2>/dev/null
pkill -f "vite" 2>/dev/null

echo "Stopping Docker infrastructure..."
docker compose -f "$ROOT_DIR/docker-compose.dev.yml" down

echo "✔ All services stopped."
