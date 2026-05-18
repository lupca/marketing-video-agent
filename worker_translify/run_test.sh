#!/bin/bash
set -e

# Set environment
export DATABASE_URL="postgresql://admin:password123@localhost:5432/video_creator"
export PYTHONPATH="/root/marketing-video-agent"

# Activate virtual environment
source /root/marketing-video-agent/worker_translify/venv/bin/activate

echo "🚀 Launching Video Translify Pipeline Test..."
python3 -m worker_translify \
  --input /root/marketing-video-agent/worker_translify/atrox_88_china.mp4 \
  --output /root/marketing-video-agent/worker_translify/atrox_88_vietnam.mp4 \
  --work-dir /root/marketing-video-agent/worker_translify/translify_tmp \
  --voice vi-VN-NamMinhNeural
