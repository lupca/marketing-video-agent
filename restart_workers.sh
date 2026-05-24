#!/bin/bash
# ============================================================
#  RESTART CELERY WORKERS
#  Kills and restarts all background Celery processes
# ============================================================

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

echo "Stopping all active Celery workers..."
pkill -f celery || true
sleep 2

# Export same environment variables as dev.sh
export IMAGEIO_FFMPEG_EXE="/usr/bin/ffmpeg"
export DATABASE_URL="postgresql://admin:password123@localhost:5432/video_creator"
export REDIS_URL="redis://localhost:6379/0"
export MINIO_ENDPOINT="localhost:9000"
export MINIO_ACCESS_KEY="minioadmin"
export MINIO_SECRET_KEY="minioadmin"
export MINIO_BUCKET_NAME="videos"
export MINIO_SECURE="false"
export PYTHONPATH="$ROOT_DIR"
export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES

echo "Starting Celery Workers..."

cd "$ROOT_DIR/worker_review"
./venv/bin/celery -A celery_worker worker -Q review_queue -n worker_review@%h --loglevel=info -c 2 &
echo "  ✔ Worker Review started."

cd "$ROOT_DIR/worker_unbox"
./venv/bin/celery -A celery_worker worker -Q unbox_queue -n worker_unbox@%h --loglevel=info -c 2 &
echo "  ✔ Worker Unbox started."

cd "$ROOT_DIR/worker_download"
./venv/bin/celery -A celery_worker worker -Q download_queue -n worker_download@%h --loglevel=info -c 3 &
echo "  ✔ Worker Download started."

cd "$ROOT_DIR/worker_slideshow"
./venv/bin/celery -A celery_worker worker -Q slideshow_queue -n worker_slideshow@%h --loglevel=info -c 2 &
echo "  ✔ Worker Slideshow started."

cd "$ROOT_DIR/worker_promotion"
./venv/bin/celery -A celery_worker worker -Q promotion_queue -n worker_promotion@%h --loglevel=info -c 2 &
echo "  ✔ Worker Promotion started."

cd "$ROOT_DIR/worker_research"
./venv/bin/celery -A celery_worker worker -Q research_queue -n worker_research@%h --loglevel=info -c 2 &
echo "  ✔ Worker Research started."

cd "$ROOT_DIR/worker_agent"
./venv/bin/celery -A celery_worker worker -Q agent_queue -n worker_agent@%h --loglevel=info -c 1 &
echo "  ✔ Worker Agent started."

cd "$ROOT_DIR/worker_text2img"
./venv/bin/celery -A celery_worker worker -Q text2img_queue -n worker_text2img@%h --loglevel=info -c 2 &
echo "  ✔ Worker Text2Img started."

cd "$ROOT_DIR/worker_tts"
./venv/bin/celery -A celery_worker worker -P solo -Q tts_queue -n worker_tts@%h --loglevel=info &
echo "  ✔ Worker TTS started."

cd "$ROOT_DIR/worker_translify"
./venv/bin/celery -A celery_worker worker -P solo -Q translify_queue -n worker_translify@%h --loglevel=info &
echo "  ✔ Worker Translify started."

echo "All Celery workers restarted successfully!"
