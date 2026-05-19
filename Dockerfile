# syntax=docker/dockerfile:1
FROM python:3.11-slim

# System deps (sklearn wheels & general build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy project metadata and source (source MUST be present to build the wheel)
COPY pyproject.toml ./
COPY src ./src
COPY ui ./ui
COPY img ./img

# Install project (include API deps). For a slim image you can do just "." instead.
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir ".[dev]"

COPY artifacts ./artifacts

# Add under your build args
ARG MODEL_POINTER=latest
ENV MODEL_POINTER=${MODEL_POINTER}

EXPOSE 8000

# Create non-root user
RUN useradd -u 10001 -m appuser

# Ensure /app and artifacts are owned by appuser
RUN mkdir -p /app/artifacts && chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Tell textclf where artifacts live
ENV ARTIFACTS_DIR=/app/artifacts

CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "textclf.api:app", "-b", "0.0.0.0:8000"]