FROM python:3.10-slim

WORKDIR /app

# Only need basic slim image for API
RUN apt-get update && apt-get install -y \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY admin-api/requirements.txt .
RUN uv pip install --system --no-cache -r requirements.txt

ENV PYTHONPATH=/app

COPY shared_core/ ./shared_core/
COPY admin-api/ ./admin-api/

CMD ["bash", "-c", "cd admin-api && uvicorn main:app --host 0.0.0.0 --port 9100"]
