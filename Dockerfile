# syntax=docker/dockerfile:1
FROM python:3.12-slim AS base

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev curl && \
    rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY pyproject.toml README.md ./
COPY src/ src/
RUN pip install --no-cache-dir .

# Copy remaining project files
COPY alembic.ini ./
COPY migrations/ migrations/

# Non-root user
RUN useradd --create-home oykos
USER oykos

EXPOSE 8080

# Web server by default. The pipeline runs as a scheduled `oykos ingest` /
# `oykos compose` / `oykos send` against the same image.
CMD ["oykos", "serve", "--host", "0.0.0.0", "--port", "8080"]
