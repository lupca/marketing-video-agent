FROM video-worker-base

WORKDIR /app

COPY worker_leader/requirements.txt .
RUN uv pip install --system --no-cache -r requirements.txt

ENV PYTHONPATH=/app

COPY shared_core/ ./shared_core/
COPY worker_leader/ ./worker_leader/

WORKDIR /app/worker_leader

CMD ["celery", "-A", "celery_worker", "worker", "-Q", "leader_queue", "--loglevel=info", "-c", "1"]
