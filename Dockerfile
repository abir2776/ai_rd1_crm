# Multi-stage build for production optimization
FROM python:3.13-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies including WeasyPrint requirements
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    libpq-dev \
    gcc \
    libmagic1 \
    # WeasyPrint dependencies
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    libcairo2 \
    libglib2.0-0 \
    shared-mime-info \
    # PDF text extraction dependencies
    poppler-utils \
    # OCR dependencies (if using pytesseract)
    tesseract-ocr \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Create non-root user FIRST
RUN useradd -m -u 1000 appuser

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY --chown=appuser:appuser . .

# Create media + static + celerybeat + PDF output directories with correct ownership
RUN mkdir -p /app/media /app/static /app/celerybeat /app/formatted_pdfs /app/resume_candidates && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Collect static (ignore errors)
RUN python manage.py collectstatic --noinput || true

EXPOSE 8000

CMD ["gunicorn", "swift_web_ai.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "4"]