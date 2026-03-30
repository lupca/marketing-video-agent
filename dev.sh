#!/bin/bash
# ============================================================
#  DEV STARTUP SCRIPT - Video Creator Platform
#  Infrastructure (DB, Redis, MinIO) → Docker
#  API, Workers, Frontend → Host machine (using venvs)
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
echo -e "${CYAN}   Video Creator Platform - Dev Environment${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# ----------------------------------------------------------
# 1. Start infrastructure via Docker
# ----------------------------------------------------------
echo -e "\n${GREEN}[1/5]${NC} Starting infrastructure (Postgres, Redis, MinIO)..."
docker compose -f docker-compose.dev.yml up -d
echo -e "${GREEN}  ✔ DB: localhost:5432  |  Redis: localhost:6379  |  MinIO: localhost:9000${NC}"

echo -e "${YELLOW}  ⏳ Waiting for Postgres...${NC}"
until docker exec video_db pg_isready -U admin -d video_creator > /dev/null 2>&1; do
  sleep 1
done
echo -e "${GREEN}  ✔ Postgres is ready${NC}"

# ----------------------------------------------------------
# 2. Setup shared venv for API (reuse if exists)
# ----------------------------------------------------------
echo -e "\n${GREEN}[2/5]${NC} Setting up Python environments..."

API_VENV="$ROOT_DIR/.venv-api"
if [ ! -d "$API_VENV" ]; then
  echo -e "${YELLOW}  Creating API venv...${NC}"
  python3 -m venv "$API_VENV"
fi
"$API_VENV/bin/pip" install --upgrade pip -q
"$API_VENV/bin/pip" install -r "$ROOT_DIR/admin-api/requirements.txt" -q
echo -e "${GREEN}  ✔ API venv ready${NC}"

# Worker Review venv
REVIEW_VENV="$ROOT_DIR/worker_review/venv"
if [ ! -d "$REVIEW_VENV" ]; then
  echo -e "${YELLOW}  Creating Worker Review venv...${NC}"
  python3 -m venv "$REVIEW_VENV"
fi
"$REVIEW_VENV/bin/pip" install --upgrade pip -q
"$REVIEW_VENV/bin/pip" install -r "$ROOT_DIR/worker_review/requirements.txt" -q
echo -e "${GREEN}  ✔ Worker Review venv ready${NC}"

# Worker Unbox venv
UNBOX_VENV="$ROOT_DIR/worker_unbox/venv"
if [ ! -d "$UNBOX_VENV" ]; then
  echo -e "${YELLOW}  Creating Worker Unbox venv...${NC}"
  python3 -m venv "$UNBOX_VENV"
fi
"$UNBOX_VENV/bin/pip" install --upgrade pip -q
"$UNBOX_VENV/bin/pip" install -r "$ROOT_DIR/worker_unbox/requirements.txt" -q
echo -e "${GREEN}  ✔ Worker Unbox venv ready${NC}"

# Worker Download venv
DOWNLOAD_VENV="$ROOT_DIR/worker_download/venv"
if [ ! -d "$DOWNLOAD_VENV" ]; then
  echo -e "${YELLOW}  Creating Worker Download venv...${NC}"
  python3 -m venv "$DOWNLOAD_VENV"
fi
"$DOWNLOAD_VENV/bin/pip" install --upgrade pip -q
"$DOWNLOAD_VENV/bin/pip" install -r "$ROOT_DIR/worker_download/requirements.txt" -q
echo -e "${GREEN}  ✔ Worker Download venv ready${NC}"

# Worker Slideshow venv
SLIDESHOW_VENV="$ROOT_DIR/worker_slideshow/venv"
if [ ! -d "$SLIDESHOW_VENV" ]; then
  echo -e "${YELLOW}  Creating Worker Slideshow venv...${NC}"
  python3 -m venv "$SLIDESHOW_VENV"
fi
"$SLIDESHOW_VENV/bin/pip" install --upgrade pip -q
"$SLIDESHOW_VENV/bin/pip" install -r "$ROOT_DIR/worker_slideshow/requirements.txt" -q
echo -e "${GREEN}  ✔ Worker Slideshow venv ready${NC}"

# Worker Promotion venv
PROMOTION_VENV="$ROOT_DIR/worker_promotion/venv"
if [ ! -d "$PROMOTION_VENV" ]; then
  echo -e "${YELLOW}  Creating Worker Promotion venv...${NC}"
  python3 -m venv "$PROMOTION_VENV"
fi
"$PROMOTION_VENV/bin/pip" install --upgrade pip -q
"$PROMOTION_VENV/bin/pip" install -r "$ROOT_DIR/worker_promotion/requirements.txt" -q
echo -e "${GREEN}  ✔ Worker Promotion venv ready${NC}"

# ----------------------------------------------------------
# 3. Common env vars
# ----------------------------------------------------------
export DATABASE_URL="postgresql://admin:password123@localhost:5432/video_creator"
export REDIS_URL="redis://localhost:6379/0"
export MINIO_ENDPOINT="localhost:9000"
export MINIO_ACCESS_KEY="minioadmin"
export MINIO_SECRET_KEY="minioadmin"
export MINIO_BUCKET_NAME="videos"
export MINIO_SECURE="false"
export PYTHONPATH="$ROOT_DIR"
export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES

echo -e "${GREEN}  ✔ Env vars exported${NC}"

# ----------------------------------------------------------
# 4. Start Admin API
# ----------------------------------------------------------
echo -e "\n${GREEN}[3/5]${NC} Starting Admin API on :8000..."
cd "$ROOT_DIR/admin-api"
"$API_VENV/bin/uvicorn" main:app --host 0.0.0.0 --port 8000 --reload &
API_PID=$!
cd "$ROOT_DIR"
echo -e "${GREEN}  ✔ API PID: $API_PID${NC}"

# ----------------------------------------------------------
# 5. Start Celery Workers
# ----------------------------------------------------------
echo -e "\n${GREEN}[4/5]${NC} Starting Celery Workers..."

cd "$ROOT_DIR/worker_review"
"$REVIEW_VENV/bin/celery" -A celery_worker worker -Q review_queue --loglevel=info -c 2 &
REVIEW_PID=$!
cd "$ROOT_DIR"
echo -e "${GREEN}  ✔ Worker Review PID: $REVIEW_PID${NC}"

cd "$ROOT_DIR/worker_unbox"
"$UNBOX_VENV/bin/celery" -A celery_worker worker -Q unbox_queue --loglevel=info -c 2 &
UNBOX_PID=$!
cd "$ROOT_DIR"
echo -e "${GREEN}  ✔ Worker Unbox PID: $UNBOX_PID${NC}"

cd "$ROOT_DIR/worker_download"
"$DOWNLOAD_VENV/bin/celery" -A celery_worker worker -Q download_queue --loglevel=info -c 3 &
DOWNLOAD_PID=$!
cd "$ROOT_DIR"
echo -e "${GREEN}  ✔ Worker Download PID: $DOWNLOAD_PID${NC}"

cd "$ROOT_DIR/worker_slideshow"
"$SLIDESHOW_VENV/bin/celery" -A celery_worker worker -Q slideshow_queue --loglevel=info -c 2 &
SLIDESHOW_PID=$!
cd "$ROOT_DIR"
echo -e "${GREEN}  ✔ Worker Slideshow PID: $SLIDESHOW_PID${NC}"

cd "$ROOT_DIR/worker_promotion"
"$PROMOTION_VENV/bin/celery" -A celery_worker worker -Q promotion_queue --loglevel=info -c 2 &
PROMOTION_PID=$!
cd "$ROOT_DIR"
echo -e "${GREEN}  ✔ Worker Promotion PID: $PROMOTION_PID${NC}"

# ----------------------------------------------------------
# 6. Start Frontend
# ----------------------------------------------------------
echo -e "\n${GREEN}[5/5]${NC} Starting Frontend on :5173..."
cd "$ROOT_DIR/frontend-admin"
npm run dev &
FRONTEND_PID=$!
cd "$ROOT_DIR"
echo -e "${GREEN}  ✔ Frontend PID: $FRONTEND_PID${NC}"

# ----------------------------------------------------------
# Summary
# ----------------------------------------------------------
echo -e "\n${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}  All services are running!${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "  ${GREEN}Frontend:${NC}      http://localhost:5173"
echo -e "  ${GREEN}API Docs:${NC}      http://localhost:8000/docs"
echo -e "  ${GREEN}MinIO Console:${NC} http://localhost:9001"
echo -e "  ${GREEN}Postgres:${NC}      localhost:5432"
echo -e "  ${GREEN}Redis:${NC}         localhost:6379"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "\n${YELLOW}Press Ctrl+C to stop all services${NC}\n"

# ----------------------------------------------------------
# Graceful shutdown
# ----------------------------------------------------------
cleanup() {
  echo -e "\n${YELLOW}Shutting down all processes...${NC}"
  kill $API_PID $REVIEW_PID $UNBOX_PID $DOWNLOAD_PID $SLIDESHOW_PID $PROMOTION_PID $FRONTEND_PID 2>/dev/null
  docker compose -f "$ROOT_DIR/docker-compose.dev.yml" down
  echo -e "${GREEN}✔ All stopped.${NC}"
  exit 0
}

trap cleanup SIGINT SIGTERM

wait
