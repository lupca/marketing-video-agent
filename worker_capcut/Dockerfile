FROM video-worker-base

WORKDIR /app

COPY worker_capcut/requirements.txt .
RUN uv pip install --system --no-cache -r requirements.txt

ENV PYTHONPATH=/app

COPY shared_core/ ./shared_core/
COPY worker_capcut/ ./worker_capcut/

WORKDIR /app/worker_capcut

CMD ["celery", "-A", "celery_worker", "worker", "-Q", "capcut_queue", "--loglevel=info", "-c", "1"]
