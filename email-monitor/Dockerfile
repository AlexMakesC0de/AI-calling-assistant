FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for attachment processing
# - tesseract-ocr: OCR for image text extraction
# - ffmpeg: Audio extraction from video files
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app
COPY . .

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:5003/health')" || exit 1

# Run app
CMD ["python", "app.py"]