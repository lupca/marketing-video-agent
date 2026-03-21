FROM python:3.10-slim

WORKDIR /app

# Install system dependencies (ffmpeg for yt-dlp merging)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY worker_download/requirements.txt .
RUN uv pip install --system --no-cache -r requirements.txt

ENV PYTHONPATH=/app

COPY shared_core/ ./shared_core/
COPY worker_download/ ./worker_download/

WORKDIR /app/worker_download

CMD ["celery", "-A", "celery_worker", "worker", "-Q", "download_queue", "--loglevel=info", "-c", "2"]
