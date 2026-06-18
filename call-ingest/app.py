"""
Call Ingest – Twilio Voice call recording handler.

Receives inbound voice calls via Twilio webhooks, records them, downloads
the MP3 recording, persists call metadata to PostgreSQL, and forwards the
audio to the voice-app /upload pipeline for transcription + AI analysis.
"""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import psycopg2
import psycopg2.pool
import requests
from flask import Flask, Response, jsonify, request
from requests.auth import HTTPBasicAuth
from twilio.request_validator import RequestValidator
from twilio.twiml.voice_response import VoiceResponse

app = Flask(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
VALIDATE_SIGNATURE = os.getenv("TWILIO_VALIDATE_SIGNATURE", "true").lower() == "true"
PUBLIC_BASE_URL = os.getenv("CALL_PUBLIC_BASE_URL", "")

VOICE_APP_UPLOAD_URL = os.getenv("VOICE_APP_UPLOAD_URL", "http://voice-app:5000/upload")
FORWARD_TIMEOUT = int(os.getenv("VOICE_APP_FORWARD_TIMEOUT", "900"))
MEDIA_DOWNLOAD_TIMEOUT = int(os.getenv("MEDIA_DOWNLOAD_TIMEOUT", "120"))

RECORDINGS_DIR = Path(os.getenv("CALL_RECORDINGS_DIR", "/data/shared/call-recordings"))
EVENTS_DIR = Path(os.getenv("CALL_EVENTS_DIR", "/data/shared/call-events"))
TMP_DIR = Path(os.getenv("CALL_TMP_DIR", "/tmp/calls"))

GREETING_TEXT = os.getenv(
    "CALL_GREETING_TEXT",
    "Thank you for calling support. Please describe your issue after the tone.",
)
MAX_RECORDING_SECONDS = int(os.getenv("CALL_MAX_RECORDING_SECONDS", "300"))

DATABASE_URL = os.getenv("DATABASE_URL", "")

RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
EVENTS_DIR.mkdir(parents=True, exist_ok=True)
TMP_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Twilio request validator
# ---------------------------------------------------------------------------
_validator = RequestValidator(TWILIO_AUTH_TOKEN) if TWILIO_AUTH_TOKEN else None

# ---------------------------------------------------------------------------
# DB connection pool
# ---------------------------------------------------------------------------
_pool: psycopg2.pool.ThreadedConnectionPool | None = None
if DATABASE_URL:
    try:
        _pool = psycopg2.pool.ThreadedConnectionPool(1, 5, DATABASE_URL)
        logger.info("DB connection pool ready")
    except Exception as exc:
        logger.warning("DB pool init failed — calls will not be persisted: %s", exc)


class _Db:
    """Context manager: borrow a connection, auto-commit or rollback."""

    def __init__(self):
        self.conn = None

    def __enter__(self):
        if _pool:
            try:
                self.conn = _pool.getconn()
            except Exception as exc:
                logger.warning("DB getconn failed: %s", exc)
        return self

    def __exit__(self, exc_type, *_):
        if self.conn:
            try:
                if exc_type:
                    self.conn.rollback()
                else:
                    self.conn.commit()
            finally:
                _pool.putconn(self.conn)
                self.conn = None

    @property
    def available(self) -> bool:
        return self.conn is not None

    def upsert_conversation(self, contact_phone: str, contact_name: str | None) -> int:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO call_conversation (contact_phone, contact_name, last_call_at)
                VALUES (%s, %s, NOW())
                ON CONFLICT (contact_phone) DO UPDATE
                  SET last_call_at = NOW(),
                      contact_name = COALESCE(EXCLUDED.contact_name, call_conversation.contact_name)
                RETURNING id
                """,
                (contact_phone, contact_name),
            )
            return cur.fetchone()[0]

    def insert_call(
        self,
        conversation_id: int,
        call_sid: str,
        direction: str,
        from_number: str | None,
        to_number: str | None,
        status: str,
        duration_seconds: int | None,
        recording_sid: str | None,
        recording_twilio_url: str | None,
        local_recording_path: str | None,
    ) -> int:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO twilio_call
                  (conversation_id, call_sid, direction, from_number, to_number,
                   status, duration_seconds, recording_sid, recording_twilio_url,
                   local_recording_path)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (call_sid) DO UPDATE
                  SET status = EXCLUDED.status,
                      duration_seconds = COALESCE(EXCLUDED.duration_seconds, twilio_call.duration_seconds),
                      recording_sid = COALESCE(EXCLUDED.recording_sid, twilio_call.recording_sid),
                      recording_twilio_url = COALESCE(EXCLUDED.recording_twilio_url, twilio_call.recording_twilio_url),
                      local_recording_path = COALESCE(EXCLUDED.local_recording_path, twilio_call.local_recording_path)
                RETURNING id
                """,
                (
                    conversation_id, call_sid, direction, from_number, to_number,
                    status, duration_seconds, recording_sid, recording_twilio_url,
                    local_recording_path,
                ),
            )
            return cur.fetchone()[0]

    def update_call_analysis(
        self, call_id: int, incident_form_id: int | None, transcript_text: str | None
    ) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                UPDATE twilio_call
                SET incident_form_id = %s, transcript_text = %s, status = 'completed'
                WHERE id = %s
                """,
                (incident_form_id, transcript_text, call_id),
            )

    def update_call_status(self, call_sid: str, status: str, error_code: str | None, error_message: str | None) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                UPDATE twilio_call
                SET status = %s, error_code = %s, error_message = %s
                WHERE call_sid = %s
                """,
                (status, error_code, error_message, call_sid),
            )

    def set_call_failed(self, call_id: int, error_message: str) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                "UPDATE twilio_call SET status = 'failed', error_message = %s WHERE id = %s",
                (error_message, call_id),
            )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_stem(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in value)
    return cleaned[:120] if cleaned else "call"


def _request_url_for_signature() -> str:
    if PUBLIC_BASE_URL:
        base = PUBLIC_BASE_URL.rstrip("/")
        return f"{base}{request.path}"
    return request.url


def _signature_valid() -> bool:
    if not VALIDATE_SIGNATURE:
        return True
    if _validator is None:
        logger.warning("Signature validation enabled but TWILIO_AUTH_TOKEN is empty — rejecting.")
        return False
    signature = request.headers.get("X-Twilio-Signature", "")
    params = request.form.to_dict(flat=True)
    return _validator.validate(_request_url_for_signature(), params, signature)


def _save_event(payload: dict, kind: str) -> Path:
    call_sid = payload.get("CallSid") or datetime.now(timezone.utc).isoformat()
    out = EVENTS_DIR / f"{kind}_{_safe_stem(str(call_sid))}.json"
    with out.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return out


def _download_recording(recording_url: str, call_sid: str) -> Path:
    mp3_url = recording_url if recording_url.endswith(".mp3") else f"{recording_url}.mp3"
    out = TMP_DIR / f"{_safe_stem(call_sid)}.mp3"
    with requests.get(
        mp3_url,
        stream=True,
        timeout=MEDIA_DOWNLOAD_TIMEOUT,
        auth=HTTPBasicAuth(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN),
        allow_redirects=True,
    ) as resp:
        resp.raise_for_status()
        with out.open("wb") as f:
            for chunk in resp.iter_content(chunk_size=1024 * 64):
                if chunk:
                    f.write(chunk)
    return out


def _persist_recording(tmp_path: Path, call_sid: str, recording_sid: str) -> Path:
    dest = RECORDINGS_DIR / f"{_safe_stem(call_sid)}_{_safe_stem(recording_sid)}.mp3"
    tmp_path.replace(dest)
    return dest


def _forward_to_voice_app(payload: dict, recording_path: Path) -> dict:
    from_number = str(payload.get("From") or "").strip()
    call_sid = str(payload.get("CallSid") or "")

    data = {
        "contact_info": from_number,
        "account_or_reference": call_sid,
        "telephony_source_number": str(payload.get("To") or "").strip(),
        "telephony_call_mode": "answered_call",
        "telephony_provider": "twilio_voice",
    }
    data = {k: v for k, v in data.items() if v}

    with recording_path.open("rb") as f:
        files = {"file": (recording_path.name, f, "audio/mpeg")}
        resp = requests.post(VOICE_APP_UPLOAD_URL, data=data, files=files, timeout=FORWARD_TIMEOUT)
    resp.raise_for_status()
    try:
        return resp.json()
    except ValueError:
        return {"status": "ok", "raw": resp.text}


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/health", methods=["GET"])
def health() -> tuple[Response, int]:
    return jsonify({
        "status": "ok",
        "twilio_configured": bool(TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN),
        "signature_validation": VALIDATE_SIGNATURE,
        "db_connected": _pool is not None,
    }), 200


@app.route("/webhooks/voice", methods=["POST"])
def voice() -> Response:
    """TwiML response for inbound calls: greet, then record."""
    if not _signature_valid():
        logger.warning("Rejected voice webhook: invalid Twilio signature")
        return Response("invalid signature", status=403)

    payload = request.form.to_dict(flat=True)
    _save_event(payload, "voice")
    logger.info(
        "Inbound call from %s to %s — CallSid=%s",
        payload.get("From"), payload.get("To"), payload.get("CallSid"),
    )

    resp = VoiceResponse()
    resp.say(GREETING_TEXT, voice="alice")
    resp.record(
        max_length=MAX_RECORDING_SECONDS,
        recording_status_callback="/webhooks/recording-status",
        recording_status_callback_method="POST",
        recording_status_callback_event="completed",
        play_beep=True,
    )
    resp.say("We did not receive a recording. Goodbye.")
    resp.hangup()

    return Response(str(resp), mimetype="application/xml")


@app.route("/webhooks/recording-status", methods=["POST"])
def recording_status() -> Response:
    """Twilio fires this when the recording is processed and ready to download."""
    if not _signature_valid():
        logger.warning("Rejected recording-status webhook: invalid Twilio signature")
        return Response("invalid signature", status=403)

    payload = request.form.to_dict(flat=True)
    _save_event(payload, "recording-status")

    call_sid = payload.get("CallSid", "")
    recording_sid = payload.get("RecordingSid", "")
    recording_url = payload.get("RecordingUrl", "")
    recording_duration = payload.get("RecordingDuration")
    from_number = payload.get("From", "")
    to_number = payload.get("To", "")

    duration = int(recording_duration) if recording_duration and recording_duration.isdigit() else None

    logger.info(
        "Recording ready — CallSid=%s RecordingSid=%s duration=%s from=%s",
        call_sid, recording_sid, duration, from_number,
    )

    if not recording_url:
        logger.error("No RecordingUrl in payload — skipping")
        return Response(status=204)

    db_call_id: int | None = None

    # 1. Persist call to DB
    try:
        with _Db() as db:
            if db.available:
                conv_id = db.upsert_conversation(from_number, None)
                db_call_id = db.insert_call(
                    conversation_id=conv_id,
                    call_sid=call_sid,
                    direction="inbound",
                    from_number=from_number,
                    to_number=to_number,
                    status="processing",
                    duration_seconds=duration,
                    recording_sid=recording_sid,
                    recording_twilio_url=recording_url,
                    local_recording_path=None,
                )
    except Exception as exc:
        logger.warning("DB insert failed for call %s: %s", call_sid, exc)

    # 2. Download recording MP3
    try:
        tmp_path = _download_recording(recording_url, call_sid)
    except Exception as exc:
        logger.exception("Failed to download recording for %s", call_sid)
        if db_call_id is not None:
            try:
                with _Db() as db:
                    if db.available:
                        db.set_call_failed(db_call_id, f"Recording download failed: {exc}")
            except Exception:
                pass
        return Response(status=204)

    # 3. Persist MP3 to permanent storage
    dest = _persist_recording(tmp_path, call_sid, recording_sid)
    if db_call_id is not None:
        try:
            with _Db() as db:
                if db.available:
                    db.conn.cursor().execute(
                        "UPDATE twilio_call SET local_recording_path = %s WHERE id = %s",
                        (str(dest), db_call_id),
                    )
                    db.conn.commit()
        except Exception as exc:
            logger.warning("Failed to update local_recording_path: %s", exc)

    # 4. Forward to voice-app pipeline
    try:
        result = _forward_to_voice_app(payload, dest)
        logger.info("Voice-app pipeline result for %s: status=%s", call_sid, result.get("pipeline", {}).get("database", {}).get("status"))

        pipeline = result.get("pipeline", {})
        incident_form_id = pipeline.get("database", {}).get("incident_form_id")
        transcript_text = pipeline.get("transcription", {}).get("text")

        if db_call_id is not None:
            try:
                with _Db() as db:
                    if db.available:
                        db.update_call_analysis(db_call_id, incident_form_id, transcript_text)
            except Exception as exc:
                logger.warning("DB analysis update failed for call %s: %s", call_sid, exc)

    except Exception as exc:
        logger.exception("Voice-app forward failed for %s", call_sid)
        if db_call_id is not None:
            try:
                with _Db() as db:
                    if db.available:
                        db.set_call_failed(db_call_id, f"Pipeline failed: {exc}")
            except Exception:
                pass

    return Response(status=204)


@app.route("/webhooks/status", methods=["POST"])
def status_callback() -> Response:
    """Call status updates (ringing, in-progress, completed, etc.)."""
    if not _signature_valid():
        return Response("invalid signature", status=403)

    payload = request.form.to_dict(flat=True)
    _save_event(payload, "status")

    call_sid = payload.get("CallSid")
    call_status = payload.get("CallStatus")
    error_code = payload.get("ErrorCode")
    error_message = payload.get("ErrorMessage")

    logger.info("Call status — sid=%s status=%s error=%s", call_sid, call_status, error_code)

    if call_sid and call_status:
        try:
            with _Db() as db:
                if db.available:
                    db.update_call_status(call_sid, call_status, error_code, error_message)
        except Exception as exc:
            logger.warning("DB status update failed for %s: %s", call_sid, exc)

    return Response(status=204)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5012, debug=True)
