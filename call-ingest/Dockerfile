FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN addgroup --system appgroup && \
    adduser --system --ingroup appgroup appuser && \
    mkdir -p /data/shared/call-recordings /data/shared/call-events /tmp/calls && \
    chown -R appuser:appgroup /app /data/shared /tmp/calls

USER appuser

EXPOSE 5012

CMD ["gunicorn", "--bind", "0.0.0.0:5012", "--workers", "2", "--timeout", "1000", "app:app"]
