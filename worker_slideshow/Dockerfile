FROM video-worker-base

WORKDIR /app

COPY worker_slideshow/requirements.txt .
RUN uv pip install --system --no-cache -r requirements.txt

ENV PYTHONPATH=/app

COPY shared_core/ ./shared_core/
COPY worker_slideshow/ ./worker_slideshow/

WORKDIR /app/worker_slideshow

CMD ["celery", "-A", "celery_worker", "worker", "-Q", "slideshow_queue", "--loglevel=info", "-c", "2"]
