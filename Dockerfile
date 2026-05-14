# =============================================================================
# Vehicle Management System — Dockerfile
# Base: python:3.12-slim
# App: Django + Gunicorn on port 3333
# collectstatic runs at container startup (via docker-compose command),
# NOT at build time, so the bind-mounted volume is populated correctly.
# =============================================================================

FROM python:3.12-slim

# -----------------------------------------------------------------------------
# Environment
# -----------------------------------------------------------------------------
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# -----------------------------------------------------------------------------
# Working directory
# -----------------------------------------------------------------------------
WORKDIR /app

# -----------------------------------------------------------------------------
# System dependencies
# -----------------------------------------------------------------------------
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    libpq-dev \
    gettext \
    libmagic1 \
    netcat-openbsd \
    curl \
    && rm -rf /var/lib/apt/lists/*

# -----------------------------------------------------------------------------
# Python dependencies
# Install before copying source so this layer is cached between code changes.
# -----------------------------------------------------------------------------
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt && \
    pip install gunicorn

# -----------------------------------------------------------------------------
# Application source
# -----------------------------------------------------------------------------
COPY src/ /app/

# -----------------------------------------------------------------------------
# Non-root user
# -----------------------------------------------------------------------------
RUN useradd -m -u 1000 appuser

# Create runtime directories and hand them to appuser.
# static_collected and media will be bind-mounted by docker-compose, so the
# directories just need to exist with the right ownership beforehand.
RUN mkdir -p /app/logs /app/static_collected /app/media && \
    chown -R appuser:appuser /app

USER appuser

# -----------------------------------------------------------------------------
# Port
# -----------------------------------------------------------------------------
EXPOSE 3333

# -----------------------------------------------------------------------------
# Default command
# collectstatic is intentionally run here rather than at build time so that
# the output lands in the bind-mounted ./src/static_collected on the host,
# making it visible to Nginx without any Docker volume indirection.
# docker-compose overrides this command to prepend migrate + collectstatic.
# -----------------------------------------------------------------------------
CMD ["gunicorn", "config.wsgi:application", \
     "--bind", "0.0.0.0:3333", \
     "--workers", "4", \
     "--threads", "2", \
     "--timeout", "120", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "--log-level", "info"]