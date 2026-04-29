# syntax=docker/dockerfile:1
FROM python:3.12-slim AS base

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev curl && \
    rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY pyproject.toml ./
COPY src/ src/
RUN pip install --no-cache-dir ".[prod]"

# Copy remaining project files
COPY alembic.ini ./
COPY migrations/ migrations/

# Non-root user
RUN useradd --create-home oykos
USER oykos

# Default: run the pipeline
CMD ["oykos"]
