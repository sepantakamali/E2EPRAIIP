# syntax=docker/dockerfile:1
FROM python:3.11-slim

# System deps (sklearn wheels & general build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy pinned runtime dependencies first for better layer caching and reproducible installs.
COPY requirements.txt ./

RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# Copy project metadata and source after dependency installation.
COPY pyproject.toml ./
COPY src ./src
COPY ui ./ui
COPY img ./img

# Install the local project without resolving unpinned dependencies again.
RUN pip install --no-cache-dir --no-deps .

# Default model selector. The actual artifacts are mounted at runtime.
ARG MODEL_POINTER=latest
ENV MODEL_POINTER=${MODEL_POINTER}

EXPOSE 8000

# Create non-root user
RUN useradd -u 10001 -m appuser

# Runtime artifact directory. Model artifacts are not baked into the image.
RUN mkdir -p /app/artifacts && chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Tell textclf where artifacts live
ENV ARTIFACTS_DIR=/app/artifacts

CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "textclf.api:app", "-b", "0.0.0.0:8000"]