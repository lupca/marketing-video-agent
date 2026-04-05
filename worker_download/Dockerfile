FROM video-worker-base

WORKDIR /app

COPY worker_download/requirements.txt .
RUN uv pip install --system --no-cache -r requirements.txt

ENV PYTHONPATH=/app

COPY shared_core/ ./shared_core/
COPY worker_download/ ./worker_download/

WORKDIR /app/worker_download

CMD ["celery", "-A", "celery_worker", "worker", "-Q", "download_queue", "--loglevel=info", "-c", "2"]
