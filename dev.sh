#!/bin/bash
# ============================================================
#  DEV STARTUP SCRIPT - Video Creator Platform
#  Infrastructure (DB, Redis, MinIO) → Docker
#  API, Workers, Frontend → Host machine (using venvs)
# ============================================================

set -e

export IMAGEIO_FFMPEG_EXE="/usr/bin/ffmpeg"

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
# 2. Setup shared venvs
# ----------------------------------------------------------
echo -e "\n${GREEN}[2/5]${NC} Setting up Shared Python environments..."

LIGHT_VENV="$ROOT_DIR/.venv-light"
if [ ! -d "$LIGHT_VENV" ]; then
  echo -e "${YELLOW}  Creating Shared Light venv...${NC}"
  if command -v python3.11 >/dev/null 2>&1; then
    python3.11 -m venv "$LIGHT_VENV"
  elif command -v python3.10 >/dev/null 2>&1; then
    python3.10 -m venv "$LIGHT_VENV"
  else
    python3 -m venv "$LIGHT_VENV"
  fi
fi
"$LIGHT_VENV/bin/pip" install --upgrade pip -q
echo -e "${YELLOW}  Installing dependencies for Light environment (API & light workers)...${NC}"
"$LIGHT_VENV/bin/pip" install -r "$ROOT_DIR/admin-api/requirements.txt" -q
"$LIGHT_VENV/bin/pip" install -r "$ROOT_DIR/worker_download/requirements.txt" -q
"$LIGHT_VENV/bin/pip" install -r "$ROOT_DIR/worker_slideshow/requirements.txt" -q
"$LIGHT_VENV/bin/pip" install -r "$ROOT_DIR/worker_tts/requirements.txt" -q
"$LIGHT_VENV/bin/pip" install -r "$ROOT_DIR/worker_chat/requirements.txt" -q
"$LIGHT_VENV/bin/pip" install -r "$ROOT_DIR/worker_leader/requirements.txt" -q
"$LIGHT_VENV/bin/pip" install -r "$ROOT_DIR/worker_text2img/requirements.txt" -q
"$LIGHT_VENV/bin/pip" install -r "$ROOT_DIR/worker_promotion/requirements.txt" -q
"$LIGHT_VENV/bin/pip" install -r "$ROOT_DIR/worker_research/requirements.txt" -q
echo -e "${GREEN}  ✔ Shared Light venv ready${NC}"

HEAVY_VENV="$ROOT_DIR/.venv-heavy"
if [ ! -d "$HEAVY_VENV" ]; then
  echo -e "${YELLOW}  Creating Shared Heavy (AI/GPU) venv...${NC}"
  if command -v python3.11 >/dev/null 2>&1; then
    python3.11 -m venv "$HEAVY_VENV"
  elif command -v python3.10 >/dev/null 2>&1; then
    python3.10 -m venv "$HEAVY_VENV"
  else
    python3 -m venv "$HEAVY_VENV"
  fi
fi
"$HEAVY_VENV/bin/pip" install --upgrade pip -q
echo -e "${YELLOW}  Installing dependencies for Heavy environment (AI/GPU)...${NC}"
"$HEAVY_VENV/bin/pip" install -r "$ROOT_DIR/worker_review/requirements.txt" -q
"$HEAVY_VENV/bin/pip" install -r "$ROOT_DIR/worker_unbox/requirements.txt" -q
"$HEAVY_VENV/bin/pip" install -r "$ROOT_DIR/worker_agent/requirements.txt" -q
"$HEAVY_VENV/bin/pip" install -r "$ROOT_DIR/worker_translify/requirements.txt" -q

# Force use of GPU-accelerated ONNX runtime and prevent CPU packages from overriding it, and force moviepy==1.0.3
echo -e "${YELLOW}  Forcing onnxruntime-gpu and moviepy==1.0.3 installation...${NC}"
"$HEAVY_VENV/bin/pip" uninstall -y onnxruntime onnxruntime-gpu moviepy -q
"$HEAVY_VENV/bin/pip" install onnxruntime-gpu moviepy==1.0.3 -q

# Fix cuDNN symlinks for PaddlePaddle
HEAVY_SITE_PACKAGES=$("$HEAVY_VENV/bin/python" -c "import site; print(site.getsitepackages()[0])" 2>/dev/null || echo "$HEAVY_VENV/lib/python3.10/site-packages")
CUDNN_LIB_PATH="$HEAVY_SITE_PACKAGES/nvidia/cudnn/lib"
CUBLAS_LIB_PATH="$HEAVY_SITE_PACKAGES/nvidia/cublas/lib"
CUFFT_LIB_PATH="$HEAVY_SITE_PACKAGES/nvidia/cufft/lib"
CURAND_LIB_PATH="$HEAVY_SITE_PACKAGES/nvidia/curand/lib"
CUSOLVER_LIB_PATH="$HEAVY_SITE_PACKAGES/nvidia/cusolver/lib"
CUSPARSE_LIB_PATH="$HEAVY_SITE_PACKAGES/nvidia/cusparse/lib"
CUDA_RT_LIB_PATH="$HEAVY_SITE_PACKAGES/nvidia/cuda_runtime/lib"
NVJITLINK_LIB_PATH="$HEAVY_SITE_PACKAGES/nvidia/nvjitlink/lib"

if [ -d "$CUDNN_LIB_PATH" ]; then
  if [ ! -f "$CUDNN_LIB_PATH/libcudnn.so" ]; then
    ln -sf libcudnn.so.9 "$CUDNN_LIB_PATH/libcudnn.so"
  fi
fi

if [ -d "$CUBLAS_LIB_PATH" ]; then
  if [ ! -f "$CUBLAS_LIB_PATH/libcublas.so" ]; then
    ln -sf libcublas.so.12 "$CUBLAS_LIB_PATH/libcublas.so"
  fi
  if [ ! -f "$CUBLAS_LIB_PATH/libcublasLt.so" ]; then
    ln -sf libcublasLt.so.12 "$CUBLAS_LIB_PATH/libcublasLt.so"
  fi
fi

echo -e "${GREEN}  ✔ Shared Heavy venv ready${NC}"

# Map individual worker variables to the shared ones for execution compatibility
API_VENV="$LIGHT_VENV"
DOWNLOAD_VENV="$LIGHT_VENV"
SLIDESHOW_VENV="$LIGHT_VENV"
PROMOTION_VENV="$LIGHT_VENV"
RESEARCH_VENV="$LIGHT_VENV"
LEADER_VENV="$LIGHT_VENV"
TEXT2IMG_VENV="$LIGHT_VENV"
TTS_VENV="$LIGHT_VENV"
CHAT_VENV="$LIGHT_VENV"

REVIEW_VENV="$HEAVY_VENV"
UNBOX_VENV="$HEAVY_VENV"
TRANSLIFY_VENV="$HEAVY_VENV"
AGENT_VENV="$HEAVY_VENV"

# ----------------------------------------------------------
# 3. Common env vars
# ----------------------------------------------------------
export LD_LIBRARY_PATH="$CUDNN_LIB_PATH:$CUBLAS_LIB_PATH:$CUFFT_LIB_PATH:$CURAND_LIB_PATH:$CUSOLVER_LIB_PATH:$CUSPARSE_LIB_PATH:$CUDA_RT_LIB_PATH:$NVJITLINK_LIB_PATH:/usr/lib/wsl/lib:$LD_LIBRARY_PATH"
export DATABASE_URL="postgresql://admin:password123@localhost:5432/video_creator"
export REDIS_URL="redis://localhost:6379/0"
export MINIO_ENDPOINT="localhost:9000"
export MINIO_ACCESS_KEY="minioadmin"
export MINIO_SECRET_KEY="minioadmin"
export MINIO_BUCKET_NAME="videos"
export MINIO_SECURE="false"
export PYTHONPATH="$ROOT_DIR"
export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES
export VECTCUT_API_URL="http://localhost:9002"

echo -e "${GREEN}  ✔ Env vars exported${NC}"

# ----------------------------------------------------------
# 4. Start Admin API
# ----------------------------------------------------------
echo -e "\n${GREEN}[3/5]${NC} Starting Admin API on :9100..."
cd "$ROOT_DIR/admin-api"
"$API_VENV/bin/uvicorn" main:app --host 0.0.0.0 --port 9100 --reload &
API_PID=$!
cd "$ROOT_DIR"
echo -e "${GREEN}  ✔ API PID: $API_PID${NC}"

# ----------------------------------------------------------
# 5. Start Celery Workers
# ----------------------------------------------------------
echo -e "\n${GREEN}[4/5]${NC} Starting Celery Workers..."

cd "$ROOT_DIR/worker_review"
"$REVIEW_VENV/bin/celery" -A celery_worker worker -Q review_queue -n worker_review@%h --loglevel=info -c 2 &
REVIEW_PID=$!
cd "$ROOT_DIR"
echo -e "${GREEN}  ✔ Worker Review PID: $REVIEW_PID${NC}"

cd "$ROOT_DIR/worker_unbox"
"$UNBOX_VENV/bin/celery" -A celery_worker worker -Q unbox_queue -n worker_unbox@%h --loglevel=info -c 2 &
UNBOX_PID=$!
cd "$ROOT_DIR"
echo -e "${GREEN}  ✔ Worker Unbox PID: $UNBOX_PID${NC}"

cd "$ROOT_DIR/worker_download"
"$DOWNLOAD_VENV/bin/celery" -A celery_worker worker -Q download_queue -n worker_download@%h --loglevel=info -c 3 &
DOWNLOAD_PID=$!
cd "$ROOT_DIR"
echo -e "${GREEN}  ✔ Worker Download PID: $DOWNLOAD_PID${NC}"

cd "$ROOT_DIR/worker_slideshow"
"$SLIDESHOW_VENV/bin/celery" -A celery_worker worker -Q slideshow_queue -n worker_slideshow@%h --loglevel=info -c 2 &
SLIDESHOW_PID=$!
cd "$ROOT_DIR"
echo -e "${GREEN}  ✔ Worker Slideshow PID: $SLIDESHOW_PID${NC}"

cd "$ROOT_DIR/worker_promotion"
"$PROMOTION_VENV/bin/celery" -A celery_worker worker -Q promotion_queue -n worker_promotion@%h --loglevel=info -c 2 &
PROMOTION_PID=$!
cd "$ROOT_DIR"
echo -e "${GREEN}  ✔ Worker Promotion PID: $PROMOTION_PID${NC}"

cd "$ROOT_DIR/worker_research"
"$RESEARCH_VENV/bin/celery" -A celery_worker worker -Q research_queue -n worker_research@%h --loglevel=info -c 2 &
RESEARCH_PID=$!
cd "$ROOT_DIR"
echo -e "${GREEN}  ✔ Worker Research PID: $RESEARCH_PID${NC}"

cd "$ROOT_DIR/worker_agent"
"$AGENT_VENV/bin/celery" -A celery_worker worker -Q agent_queue -n worker_agent@%h --loglevel=info -c 1 &
AGENT_PID=$!
cd "$ROOT_DIR"
echo -e "${GREEN}  ✔ Worker Agent PID: $AGENT_PID${NC}"

cd "$ROOT_DIR/worker_leader"
"$LEADER_VENV/bin/celery" -A celery_worker worker -Q leader_queue -n worker_leader@%h --loglevel=info -c 1 &
LEADER_PID=$!
cd "$ROOT_DIR"
echo -e "${GREEN}  ✔ Worker Leader PID: $LEADER_PID${NC}"

cd "$ROOT_DIR/worker_text2img"
"$TEXT2IMG_VENV/bin/celery" -A celery_worker worker -Q text2img_queue -n worker_text2img@%h --loglevel=info -c 2 &
TEXT2IMG_PID=$!
cd "$ROOT_DIR"
echo -e "${GREEN}  ✔ Worker Text2Img PID: $TEXT2IMG_PID${NC}"

cd "$ROOT_DIR/worker_tts"
"$TTS_VENV/bin/celery" -A celery_worker worker -P solo -Q tts_queue -n worker_tts@%h --loglevel=info &
TTS_PID=$!
cd "$ROOT_DIR"
echo -e "${GREEN}  ✔ Worker TTS PID: $TTS_PID${NC}"

cd "$ROOT_DIR/worker_chat"
"$CHAT_VENV/bin/celery" -A celery_worker worker -P solo -Q chat_queue -n worker_chat@%h --loglevel=info &
CHAT_PID=$!
cd "$ROOT_DIR"
echo -e "${GREEN}  ✔ Worker Chat PID: $CHAT_PID${NC}"

cd "$ROOT_DIR/worker_translify"
"$TRANSLIFY_VENV/bin/celery" -A celery_worker worker -P solo -Q translify_queue -n worker_translify@%h --loglevel=info &
TRANSLIFY_PID=$!
cd "$ROOT_DIR"
echo -e "${GREEN}  ✔ Worker Translify PID: $TRANSLIFY_PID${NC}"

cd "$ROOT_DIR/worker_capcut"
PYTHONPATH="$ROOT_DIR" "$ROOT_DIR/.venv-api/bin/celery" -A celery_worker worker -P solo -Q capcut_queue -n worker_capcut@%h --loglevel=info &
CAPCUT_PID=$!
cd "$ROOT_DIR"
echo -e "${GREEN}  ✔ Worker CapCut PID: $CAPCUT_PID${NC}"

# ----------------------------------------------------------
# 6. Start Frontend
# ----------------------------------------------------------
echo -e "\n${GREEN}[5/5]${NC} Starting Frontend on :9173..."
cd "$ROOT_DIR/frontend-admin"
npm run dev -- --port 9173 &
FRONTEND_PID=$!
cd "$ROOT_DIR"
echo -e "${GREEN}  ✔ Frontend PID: $FRONTEND_PID${NC}"

# ----------------------------------------------------------
# Summary
# ----------------------------------------------------------
echo -e "\n${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}  All services are running!${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "  ${GREEN}Frontend:${NC}      http://localhost:9173"
echo -e "  ${GREEN}API Docs:${NC}      http://localhost:9100/docs"
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
  kill $API_PID $REVIEW_PID $UNBOX_PID $DOWNLOAD_PID $SLIDESHOW_PID $PROMOTION_PID $RESEARCH_PID $TEXT2IMG_PID $TTS_PID $CHAT_PID $AGENT_PID $LEADER_PID $TRANSLIFY_PID $CAPCUT_PID $FRONTEND_PID 2>/dev/null
  docker compose -f "$ROOT_DIR/docker-compose.dev.yml" down
  echo -e "${GREEN}✔ All stopped.${NC}"
  exit 0
}

trap cleanup SIGINT SIGTERM

wait
