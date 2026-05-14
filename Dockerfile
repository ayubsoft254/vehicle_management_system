# =============================================================================
# Vehicle Management System - Dockerfile
# =============================================================================

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    libpq-dev \
    gettext \
    libmagic1 \
    netcat-openbsd \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Use app requirements file directly to avoid host encoding inconsistencies.
COPY src/requirements.txt /tmp/requirements.txt
RUN pip install --upgrade pip && \
    pip install -r /tmp/requirements.txt && \
    pip install gunicorn

COPY entrypoint.sh /entrypoint.sh
RUN sed -i 's/\r$//' /entrypoint.sh && chmod +x /entrypoint.sh

COPY src/ /app/

RUN useradd -m -u 1000 appuser && \
    mkdir -p /app/logs /app/static_collected /app/media && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 3333

ENTRYPOINT ["/entrypoint.sh"]

CMD ["gunicorn", "config.wsgi:application", \
     "--bind", "0.0.0.0:3333", \
     "--workers", "4", \
     "--threads", "2", \
     "--timeout", "120", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "--log-level", "info"]