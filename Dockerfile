# Medical Data Validator - Production Docker Image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV DEBIAN_FRONTEND=noninteractive
ENV PORT=8000

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy pyproject.toml and package files first for better caching
COPY pyproject.toml .
COPY medical_data_validator/ ./medical_data_validator/

# Install the package with all web dependencies
RUN pip install --no-cache-dir -e ".[web-all]"

# Copy the rest of the application code
COPY . .

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app
USER app

# Expose port (Railway will override this)
EXPOSE $PORT

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:$PORT/api/health || exit 1

# Default command for Railway
CMD gunicorn wsgi:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120 