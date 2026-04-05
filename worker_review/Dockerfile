FROM video-worker-base

WORKDIR /app

COPY worker_review/requirements.txt .
RUN uv pip install --system --no-cache -r requirements.txt

ENV PYTHONPATH=/app

COPY shared_core/ ./shared_core/
COPY worker_review/ ./worker_review/

WORKDIR /app/worker_review

CMD ["celery", "-A", "celery_worker", "worker", "-Q", "review_queue", "--loglevel=info", "-c", "1"]
