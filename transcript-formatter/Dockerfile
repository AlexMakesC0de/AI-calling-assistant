###############################################################################
# Transcript Formatter – multi-stage production build
###############################################################################
FROM python:3.12-slim AS base

# Prevent Python from writing .pyc and enable unbuffered stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies in a separate layer for caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

# Non-root user for security
RUN addgroup --system appgroup && \
    adduser --system --ingroup appgroup appuser && \
    mkdir -p /data/shared/templates && \
    chown -R appuser:appgroup /app /data/shared
USER appuser

EXPOSE 5001

# Use threaded workers so long Ollama calls do not block all requests.
CMD ["gunicorn", "--bind", "0.0.0.0:5001", "--workers", "2", "--worker-class", "gthread", "--threads", "4", "--timeout", "900", "--graceful-timeout", "60", "app:app"]
