# For GPU Support, consider changing to a CUDA base image:
# FROM nvidia/cuda:12.1.0-runtime-ubuntu22.04
FROM video-worker-base

WORKDIR /app

COPY worker_translify/requirements.txt .
RUN uv pip install --system --no-cache -r requirements.txt

ENV PYTHONPATH=/app

COPY shared_core/ ./shared_core/
COPY worker_translify/ ./worker_translify/

WORKDIR /app/worker_translify

CMD ["celery", "-A", "celery_worker", "worker", "-P", "solo", "-Q", "translify_queue", "--loglevel=info"]
