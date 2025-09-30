# Multi-stage Dockerfile for both development and production
FROM python:3.11-slim as base

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    libpq-dev \
    netcat-traditional \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir jupyter notebook ipykernel

# Setup Jupyter configuration directory
RUN mkdir -p /root/.jupyter

# Copy Jupyter configuration
COPY jupyter_config.py /root/.jupyter/jupyter_notebook_config.py

# Production stage
FROM base as production
RUN pip install gunicorn

# Copy project files
COPY --chown=nobody:nogroup . .

# Create necessary directories
RUN mkdir -p /app/media/uploads/original /app/static /app/logs && \
    chown -R nobody:nogroup /app/media /app/static /app/logs

# Switch to non-root user
USER nobody

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/health/ || exit 1

# Expose port
EXPOSE 8000

# Development stage
FROM base as development

# Copy project files
COPY . .

# Create media directory
RUN mkdir -p media/uploads/original

# Expose port
EXPOSE 8000