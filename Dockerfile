# syntax=docker/dockerfile:1
FROM python:3.11-slim

# System deps (sklearn wheels & general build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy project metadata and source (source MUST be present to build the wheel)
COPY pyproject.toml ./
COPY src ./src

# Install project (include API deps). For a slim image you can do just "." instead.
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir ".[dev]"

# Optional: if you want a default model baked in, uncomment:
# COPY artifacts ./artifacts

# Add under your build args
ARG MODEL_POINTER=latest
ENV MODEL_POINTER=${MODEL_POINTER}

EXPOSE 8000
CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", \
     "--workers", "2", "--threads", "4", "--timeout", "60", \
     "--bind", "0.0.0.0:8000", "textclf.api:app"]

# create non-root user and switch
RUN useradd -u 10001 -m appuser
USER appuser