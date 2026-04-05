FROM video-worker-base

WORKDIR /app

COPY worker_unbox/requirements.txt .
RUN uv pip install --system --no-cache -r requirements.txt

ENV PYTHONPATH=/app

COPY shared_core/ ./shared_core/
COPY worker_unbox/ ./worker_unbox/

WORKDIR /app/worker_unbox

CMD ["celery", "-A", "celery_worker", "worker", "-Q", "unbox_queue", "--loglevel=info", "-c", "1"]
