import json
import logging
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

import requests
from flask import Flask, jsonify, request

app = Flask(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)

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


def _require_auth() -> bool:
    if not WEBHOOK_SHARED_TOKEN:
        return True
    token = request.headers.get("X-Telephony-Token", "")
    return token == WEBHOOK_SHARED_TOKEN


def _safe_stem(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in value)
    return cleaned[:120] if cleaned else "event"


def _save_event(event: dict) -> Path:
    event_id = str(event.get("event_id") or event.get("call_id") or datetime.now(timezone.utc).timestamp())
    event_file = EVENTS_DIR / f"{_safe_stem(event_id)}.json"
    with event_file.open("w", encoding="utf-8") as f:
        json.dump(event, f, ensure_ascii=False, indent=2)
    return event_file


def _download_recording(recording_url: str, call_id: str) -> Path:
    out_file = TMP_DIR / f"{_safe_stem(call_id)}.wav"
    headers = {}
    if RECORDING_AUTH_HEADER and RECORDING_AUTH_VALUE:
        headers[RECORDING_AUTH_HEADER] = RECORDING_AUTH_VALUE

    with requests.get(recording_url, stream=True, timeout=RECORDING_DOWNLOAD_TIMEOUT, headers=headers) as resp:
        resp.raise_for_status()
        with out_file.open("wb") as f:
            for chunk in resp.iter_content(chunk_size=1024 * 64):
                if chunk:
                    f.write(chunk)
    return out_file


def _resolve_recording_path(event: dict) -> Path:
    local_path = event.get("recording_path")
    if local_path:
        path = Path(local_path)
        if not path.exists():
            raise FileNotFoundError(f"recording_path does not exist: {local_path}")
        return path

    recording_url = event.get("recording_url")
    if not recording_url:
        raise ValueError("event must include recording_url or recording_path")

    call_id = str(event.get("call_id") or event.get("event_id") or "call")
    return _download_recording(recording_url, call_id)


def _forward_to_voice_app(event: dict, recording_path: Path) -> dict:
    caller = str(event.get("caller_id") or "").strip()
    source = str(event.get("source_number") or "").strip()
    call_mode = "answered_call" if event.get("answered") else "voicemail"

    data = {
        "contact_info": caller,
        "account_or_reference": str(event.get("call_id") or ""),
        "telephony_source_number": source,
        "telephony_call_mode": call_mode,
        "telephony_provider": str(event.get("provider") or ""),
    }
    data = {k: v for k, v in data.items() if v}

    mime_types = {
        ".wav": "audio/wav",
        ".ogg": "audio/ogg",
        ".mp3": "audio/mpeg",
        ".gsm": "audio/x-gsm",
    }
    mime = mime_types.get(recording_path.suffix.lower(), "application/octet-stream")

    with recording_path.open("rb") as f:
        files = {"file": (recording_path.name, f, mime)}
        resp = requests.post(
            VOICE_APP_UPLOAD_URL,
            data=data,
            files=files,
            timeout=FORWARD_TIMEOUT,
        )
    resp.raise_for_status()
    return resp.json()


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


@app.route("/webhooks/recording-complete", methods=["POST"])
def recording_complete():
    if not _require_auth():
        return jsonify({"error": "unauthorized"}), 401

    payload = request.get_json(silent=True)
    if payload is None:
        return jsonify({"error": "Request body must be valid JSON."}), 400

    try:
        event_file = _save_event(payload)
        recording_path = _resolve_recording_path(payload)
        pipeline_result = _forward_to_voice_app(payload, recording_path)

        # Cleanup temporary downloads only; keep explicit local recording_path untouched.
        if payload.get("recording_url") and recording_path.exists():
            recording_path.unlink(missing_ok=True)

        return jsonify(
            {
                "status": "processed",
                "event_file": str(event_file),
                "voice_app": pipeline_result,
            }
        ), 200
    except Exception as exc:
        logger.exception("Failed to process telephony recording event")
        return jsonify({"status": "failed", "error": str(exc)}), 502


@app.route("/webhooks/example-payload", methods=["GET"])
def example_payload():
    return jsonify(
        {
            "provider": "pbx",
            "event_id": "evt-123",
            "call_id": "call-abc",
            "source_number": "+31-10-0000000",
            "destination_number": "+31-10-1111111",
            "caller_id": "+31-6-12345678",
            "answered": True,
            "recording_url": "https://example.invalid/recordings/call-abc.wav",
            "recording_path": "/data/shared/uploads/test_call.wav",
            "started_at": "2026-03-26T09:00:00Z",
            "ended_at": "2026-03-26T09:03:20Z",
        }
    ), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5010, debug=True)
