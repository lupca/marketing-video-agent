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
export VECTCUT_API_URL="http://localhost:9002"

echo "Starting Celery Workers with nohup..."

cd "$ROOT_DIR/worker_review"
nohup ./venv/bin/celery -A celery_worker worker -Q review_queue -n worker_review@%h --loglevel=info -c 2 > "$ROOT_DIR/worker_review.log" 2>&1 &
echo "  ✔ Worker Review started."

cd "$ROOT_DIR/worker_unbox"
nohup ./venv/bin/celery -A celery_worker worker -Q unbox_queue -n worker_unbox@%h --loglevel=info -c 2 > "$ROOT_DIR/worker_unbox.log" 2>&1 &
echo "  ✔ Worker Unbox started."

cd "$ROOT_DIR/worker_download"
nohup ./venv/bin/celery -A celery_worker worker -Q download_queue -n worker_download@%h --loglevel=info -c 3 > "$ROOT_DIR/worker_download.log" 2>&1 &
echo "  ✔ Worker Download started."

cd "$ROOT_DIR/worker_slideshow"
nohup ./venv/bin/celery -A celery_worker worker -Q slideshow_queue -n worker_slideshow@%h --loglevel=info -c 2 > "$ROOT_DIR/worker_slideshow.log" 2>&1 &
echo "  ✔ Worker Slideshow started."

cd "$ROOT_DIR/worker_promotion"
nohup ./venv/bin/celery -A celery_worker worker -Q promotion_queue -n worker_promotion@%h --loglevel=info -c 2 > "$ROOT_DIR/worker_promotion.log" 2>&1 &
echo "  ✔ Worker Promotion started."

cd "$ROOT_DIR/worker_research"
nohup ./venv/bin/celery -A celery_worker worker -Q research_queue -n worker_research@%h --loglevel=info -c 2 > "$ROOT_DIR/worker_research.log" 2>&1 &
echo "  ✔ Worker Research started."

cd "$ROOT_DIR/worker_agent"
nohup ./venv/bin/celery -A celery_worker worker -Q agent_queue -n worker_agent@%h --loglevel=info -c 1 > "$ROOT_DIR/worker_agent.log" 2>&1 &
echo "  ✔ Worker Agent started."

cd "$ROOT_DIR/worker_text2img"
nohup ./venv/bin/celery -A celery_worker worker -Q text2img_queue -n worker_text2img@%h --loglevel=info -c 2 > "$ROOT_DIR/worker_text2img.log" 2>&1 &
echo "  ✔ Worker Text2Img started."

cd "$ROOT_DIR/worker_tts"
nohup ./venv/bin/celery -A celery_worker worker -P solo -Q tts_queue -n worker_tts@%h --loglevel=info > "$ROOT_DIR/worker_tts.log" 2>&1 &
echo "  ✔ Worker TTS started."

cd "$ROOT_DIR/worker_chat"
nohup ./venv/bin/celery -A celery_worker worker -P solo -Q chat_queue -n worker_chat@%h --loglevel=info > "$ROOT_DIR/worker_chat.log" 2>&1 &
echo "  ✔ Worker Chat started."

cd "$ROOT_DIR/worker_translify"
nohup ./venv/bin/celery -A celery_worker worker -P solo -Q translify_queue -n worker_translify@%h --loglevel=info > "$ROOT_DIR/worker_translify.log" 2>&1 &
echo "  ✔ Worker Translify started."

cd "$ROOT_DIR/worker_leader"
nohup ./venv/bin/celery -A celery_worker worker -Q leader_queue -n worker_leader@%h --loglevel=info -c 1 > "$ROOT_DIR/worker_leader.log" 2>&1 &
echo "  ✔ Worker Leader started."

cd "$ROOT_DIR/worker_capcut"
nohup env PYTHONPATH="$ROOT_DIR" "$ROOT_DIR/.venv-api/bin/celery" -A celery_worker worker -P solo -Q capcut_queue -n worker_capcut@%h --loglevel=info > "$ROOT_DIR/worker_capcut.log" 2>&1 &
echo "  ✔ Worker CapCut started."

# Detach all background jobs so they remain alive when shell exits
disown -a

echo "All Celery workers restarted persistently!"
