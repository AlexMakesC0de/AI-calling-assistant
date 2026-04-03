import os
from pathlib import Path

VOICE_APP_UPLOAD_URL = os.getenv("VOICE_APP_UPLOAD_URL", "http://localhost:5000/upload")
WEBHOOK_SHARED_TOKEN = os.getenv("TELEPHONY_WEBHOOK_TOKEN", "")
EVENTS_DIR = Path(os.getenv("TELEPHONY_EVENTS_DIR", "/data/shared/telephony-events"))
TMP_DIR = Path(os.getenv("TELEPHONY_TMP_DIR", "/tmp/telephony"))
RECORDING_DOWNLOAD_TIMEOUT = int(os.getenv("RECORDING_DOWNLOAD_TIMEOUT", "120"))
FORWARD_TIMEOUT = int(os.getenv("VOICE_APP_FORWARD_TIMEOUT", "900"))
RECORDING_AUTH_HEADER = os.getenv("RECORDING_AUTH_HEADER", "")
RECORDING_AUTH_VALUE = os.getenv("RECORDING_AUTH_VALUE", "")

EVENTS_DIR.mkdir(parents=True, exist_ok=True)
TMP_DIR.mkdir(parents=True, exist_ok=True)
