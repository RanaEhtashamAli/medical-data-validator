# ── Stage 1: builder ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc g++ curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Copy only dependency manifests first — leverages layer cache
COPY pyproject.toml .
COPY medical_data_validator/ ./medical_data_validator/

# Install the package with all extras into an isolated prefix
RUN pip install --prefix=/install -e ".[all]"


# ── Stage 2: runtime ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    PORT=8000 \
    FLASK_ENV=production \
    # Audit + job store location inside the container
    AUDIT_DB_DIR=/data \
    JOBS_DB_DIR=/data \
    REGISTRY_DB_PATH=/data/registry.db

# Runtime system deps only
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder
COPY --from=builder /install /usr/local

WORKDIR /app

# Copy application code
COPY --from=builder /build/medical_data_validator ./medical_data_validator
COPY pyproject.toml wsgi.py api.py launch_dashboard.py ./

# Persistent data directory (mount a volume here in production)
RUN mkdir -p /data && chmod 777 /data

# Non-root user
RUN useradd --create-home --shell /bin/bash --uid 1001 appuser \
    && chown -R appuser:appuser /app /data
USER appuser

EXPOSE $PORT

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -sf http://localhost:${PORT}/api/health || exit 1

# Default: run the gunicorn API server
CMD ["sh", "-c", "gunicorn wsgi:app --bind 0.0.0.0:${PORT} --workers ${GUNICORN_WORKERS:-2} --threads ${GUNICORN_THREADS:-4} --timeout 120 --access-logfile - --error-logfile -"]
