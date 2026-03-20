FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    imagemagick \
    libsm6 \
    libxext6 \
    && rm -rf /var/lib/apt/lists/*

# Fix ImageMagick policy for moviepy
RUN sed -i 's/none/read,write/g' /etc/ImageMagick-6/policy.xml || true

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY worker_unbox/requirements.txt .
RUN uv pip install --system --no-cache -r requirements.txt

ENV PYTHONPATH=/app

COPY shared_core/ ./shared_core/
COPY worker_unbox/ ./worker_unbox/

WORKDIR /app/worker_unbox

CMD ["celery", "-A", "celery_worker", "worker", "-Q", "unbox_queue", "--loglevel=info", "-c", "1"]
