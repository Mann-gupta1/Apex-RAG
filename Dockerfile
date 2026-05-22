# Apex RAG API container (FastAPI + gRPC)
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        ffmpeg \
        libgl1 \
        libglib2.0-0 \
        tesseract-ocr \
        poppler-utils \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml ./
COPY src/ ./src/
COPY proto/ ./proto/
COPY config/ ./config/
COPY alembic.ini ./
COPY alembic/ ./alembic/
COPY README.md ./

RUN pip install --upgrade pip && \
    pip install ".[retrieval,agent,api,eval,safety]"

ENV PYTHONPATH=/app/src

EXPOSE 8000 50051

CMD ["uvicorn", "apex.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
