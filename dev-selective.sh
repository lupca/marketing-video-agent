#!/bin/bash
# ============================================================
#  SELECTIVE WORKER STARTUP - Video Creator Platform
#  Starts only workers enabled in the database.
# ============================================================

set -e

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

# Colors
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}   Video Creator Platform - Selective Startup${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# 1. Start core infra via Docker
echo -e "\n${GREEN}[1/3]${NC} Starting core infrastructure..."
docker compose -f docker-compose.dev.yml up -d
echo -e "${GREEN}  ✔ Postgres, Redis, MinIO are running${NC}"

# 2. Fetch enabled workers from database
echo -e "\n${GREEN}[2/3]${NC} Checking enabled workers in database..."

# Ensure environment is set for the python call
export PYTHONPATH="$ROOT_DIR"
export DATABASE_URL="postgresql://admin:password123@localhost:5432/video_creator"

ENABLED_WORKERS=$(python3 -c "
import sys
import os
sys.path.insert(0, os.getcwd())
from shared_core.database import SessionLocal
from shared_core.models import WorkerConfig
try:
    db = SessionLocal()
    configs = db.query(WorkerConfig).filter(WorkerConfig.is_enabled == True).all()
    print(' '.join([c.worker_type for c in configs]))
    db.close()
except Exception as e:
    # Fallback to defaults if DB isn't ready or tables missing
    print('review unbox download agent')
")

if [ -z "$ENABLED_WORKERS" ]; then
    echo -e "${YELLOW}  ⚠️  No workers enabled in DB. Running init...${NC}"
    python3 init_worker_configs.py --init
    # Re-fetch
    ENABLED_WORKERS=$(python3 -c "from shared_core.database import SessionLocal; from shared_core.models import WorkerConfig; db = SessionLocal(); configs = db.query(WorkerConfig).filter(WorkerConfig.is_enabled == True).all(); print(' '.join([c.worker_type for c in configs])); db.close()")
fi

echo -e "${GREEN}  ✔ Workers to start: ${CYAN}$ENABLED_WORKERS${NC}"

# 3. Start Workers
echo -e "\n${GREEN}[3/3]${NC} Launching worker processes..."

for WORKER in $ENABLED_WORKERS; do
    WORKER_DIR="$ROOT_DIR/worker_$WORKER"
    if [ ! -d "$WORKER_DIR" ]; then
        echo -e "${RED}  ✗ Directory not found: $WORKER_DIR${NC}"
        continue
    fi
    
    VENV="$WORKER_DIR/venv"
    if [ ! -d "$VENV" ]; then
        echo -e "${YELLOW}  Creating venv for $WORKER...${NC}"
        python3 -m venv "$VENV"
        "$VENV/bin/pip" install --upgrade pip -q
        "$VENV/bin/pip" install -r "$WORKER_DIR/requirements.txt" -q
    fi
    
    echo -e "${GREEN}  🚀 Starting worker_$WORKER...${NC}"
    QUEUE="${WORKER}_queue"
    # Use -n to make worker names unique
    cd "$WORKER_DIR"
    "$VENV/bin/celery" -A celery_worker worker -Q "$QUEUE" -n "worker_${WORKER}@%h" --loglevel=info --concurrency=1 &
    cd "$ROOT_DIR"
done

echo -e "\n${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}   Selective Startup Complete!${NC}"
echo -e "${YELLOW}   Press Ctrl+C to stop (if using wait) or kill manually.${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Keep script alive to manage background processes if needed
wait
