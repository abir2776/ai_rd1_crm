# Base image
FROM python:3.13-slim AS base

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        apt-utils \
        ca-certificates \
        gnupg \
        dirmngr \
        wget \
        build-essential \
        gcc \
        libffi-dev \
        libpq-dev \
        postgresql-client \
        libmagic1 \
        libpango-1.0-0 \
        libpangocairo-1.0-0 \
        libgdk-pixbuf-2.0-0 \
        libcairo2 \
        libglib2.0-0 \
        shared-mime-info \
        poppler-utils \
        tesseract-ocr && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 appuser

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY --chown=appuser:appuser . .

# Create directories and set permissions
RUN mkdir -p media static celerybeat formatted_pdfs resume_candidates && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Collect static files
RUN python manage.py collectstatic --noinput || true

# Expose port
EXPOSE 8000

# Default command
CMD ["gunicorn", "swift_web_ai.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "4"]
