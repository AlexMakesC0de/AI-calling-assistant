###############################################################################
# Transcriber – Whisper + Speaker Diarization
###############################################################################
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/home/appuser \
    XDG_CACHE_HOME=/models/.cache \
    HF_HOME=/models/.cache/huggingface

# System dependencies for audio processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies (heavy ML libs — cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

# Non-root user for security
RUN addgroup --system appgroup && \
    adduser --system --ingroup appgroup --home /home/appuser appuser && \
    mkdir -p /home/appuser /models/speechbrain /models/.cache/huggingface /data/shared && \
    chown -R appuser:appgroup /app /models /data/shared /home/appuser
USER appuser

EXPOSE 9000

# Higher timeout for model loading on first request + long transcriptions
CMD ["gunicorn", "--bind", "0.0.0.0:9000", "--workers", "1", "--worker-class", "gthread", "--threads", "4", "--timeout", "600", "app:app"]
