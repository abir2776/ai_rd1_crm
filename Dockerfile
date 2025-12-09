FROM python:3.13-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# Update and install minimal build tools first
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    libpq-dev \
    postgresql-client \
    libmagic1 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install remaining system libraries in a separate layer
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libglib2.0-0 \
    shared-mime-info \
    poppler-utils \
    tesseract-ocr && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 appuser

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY --chown=appuser:appuser . .

# Create directories
RUN mkdir -p media static celerybeat formatted_pdfs resume_candidates && \
    chown -R appuser:appuser /app

USER appuser

RUN python manage.py collectstatic --noinput || true

EXPOSE 8000

CMD ["gunicorn", "swift_web_ai.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "4"]
