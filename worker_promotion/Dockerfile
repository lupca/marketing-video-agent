FROM video-worker-base

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY worker_promotion/requirements.txt .
RUN uv pip install --system --no-cache -r requirements.txt

ENV PYTHONPATH=/app

COPY shared_core/ ./shared_core/
COPY worker_promotion/ ./worker_promotion/

WORKDIR /app/worker_promotion

CMD ["celery", "-A", "celery_worker", "worker", "-Q", "promotion_queue", "--loglevel=info", "-c", "1"]
