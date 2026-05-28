"""
WhatsApp Ingest – Twilio WhatsApp prototype.

Receives inbound WhatsApp messages (text, media, voice notes) from the
Twilio sandbox or a production WhatsApp sender, persists every message to
the shared PostgreSQL DB, forwards audio media to the existing voice-app
/upload pipeline, and exposes /send for outbound text + media replies.
"""

import json
import logging
import mimetypes
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import psycopg2
import psycopg2.pool
import requests
from flask import Flask, Response, jsonify, request
from requests.auth import HTTPBasicAuth
from twilio.request_validator import RequestValidator
from twilio.rest import Client as TwilioClient
from twilio.twiml.messaging_response import MessagingResponse

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
TWILIO_WHATSAPP_FROM = os.getenv("TWILIO_WHATSAPP_FROM", "")
VALIDATE_SIGNATURE = os.getenv("TWILIO_VALIDATE_SIGNATURE", "true").lower() == "true"
PUBLIC_BASE_URL = os.getenv("WHATSAPP_PUBLIC_BASE_URL", "")

VOICE_APP_UPLOAD_URL = os.getenv("VOICE_APP_UPLOAD_URL", "http://voice-app:5000/upload")
FORWARD_TIMEOUT = int(os.getenv("VOICE_APP_FORWARD_TIMEOUT", "900"))
MEDIA_DOWNLOAD_TIMEOUT = int(os.getenv("MEDIA_DOWNLOAD_TIMEOUT", "120"))

EVENTS_DIR = Path(os.getenv("WHATSAPP_EVENTS_DIR", "/data/shared/whatsapp-events"))
MEDIA_DIR = Path(os.getenv("WHATSAPP_MEDIA_DIR", "/data/shared/whatsapp-media"))
TMP_DIR = Path(os.getenv("WHATSAPP_TMP_DIR", "/tmp/whatsapp"))

AUTO_ACK_TEXT = os.getenv("WHATSAPP_AUTO_ACK_TEXT", "Got it — processing your message.")
AUTO_ACK_VOICE = os.getenv("WHATSAPP_AUTO_ACK_VOICE", "Got your voice note — transcribing now.")
SILENT_REPLY = os.getenv("WHATSAPP_SILENT_REPLY", "false").lower() == "true"

DATABASE_URL = os.getenv("DATABASE_URL", "")

EVENTS_DIR.mkdir(parents=True, exist_ok=True)
MEDIA_DIR.mkdir(parents=True, exist_ok=True)
TMP_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Twilio clients
# ---------------------------------------------------------------------------
_validator = RequestValidator(TWILIO_AUTH_TOKEN) if TWILIO_AUTH_TOKEN else None
_twilio: TwilioClient | None = None
if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
    _twilio = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# ---------------------------------------------------------------------------
# DB connection pool (non-fatal if DATABASE_URL is absent)
# ---------------------------------------------------------------------------
_pool: psycopg2.pool.ThreadedConnectionPool | None = None
if DATABASE_URL:
    try:
        _pool = psycopg2.pool.ThreadedConnectionPool(1, 5, DATABASE_URL)
        logger.info("DB connection pool ready")
    except Exception as exc:
        logger.warning("DB pool init failed — messages will not be persisted to DB: %s", exc)


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
                INSERT INTO whatsapp_conversation (contact_phone, contact_name, last_message_at)
                VALUES (%s, %s, NOW())
                ON CONFLICT (contact_phone) DO UPDATE
                  SET last_message_at = NOW(),
                      contact_name = COALESCE(EXCLUDED.contact_name, whatsapp_conversation.contact_name)
                RETURNING id
                """,
                (contact_phone, contact_name),
            )
            return cur.fetchone()[0]

    def insert_message(
        self,
        conversation_id: int,
        twilio_sid: str | None,
        direction: str,
        status: str,
        message_type: str,
        body: str | None,
        raw_payload: dict,
    ) -> int:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO whatsapp_message
                  (conversation_id, twilio_sid, direction, status, message_type, body, raw_payload)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    conversation_id,
                    twilio_sid,
                    direction,
                    status,
                    message_type,
                    body,
                    json.dumps(raw_payload),
                ),
            )
            return cur.fetchone()[0]

    def insert_media(
        self,
        message_id: int,
        index: int,
        twilio_url: str,
        content_type: str,
        local_path: str | None,
        file_size: int | None,
    ) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO whatsapp_media
                  (message_id, media_index, twilio_url, content_type, local_path, file_size_bytes)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (message_id, index, twilio_url, content_type, local_path, file_size),
            )

    def update_status(self, twilio_sid: str, status: str) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                "UPDATE whatsapp_message SET status = %s, updated_at = NOW() WHERE twilio_sid = %s",
                (status, twilio_sid),
            )

    def set_incident_form(self, message_id: int, incident_form_id: int) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                "UPDATE whatsapp_message SET incident_form_id = %s, updated_at = NOW() WHERE id = %s",
                (incident_form_id, message_id),
            )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_stem(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in value)
    return cleaned[:120] if cleaned else "msg"


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
    sid = payload.get("MessageSid") or payload.get("SmsMessageSid") or datetime.now(timezone.utc).isoformat()
    out = EVENTS_DIR / f"{kind}_{_safe_stem(str(sid))}.json"
    with out.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return out


def _infer_message_type(num_media: int, payload: dict) -> str:
    if num_media == 0:
        return "text"
    ct = payload.get("MediaContentType0", "")
    if ct.startswith("audio/"):
        return "voice_note"
    if ct.startswith("image/"):
        return "image"
    if ct.startswith("video/"):
        return "video"
    return "document"


def _download_media(media_url: str, message_sid: str, index: int, content_type: str) -> Path:
    suffix = mimetypes.guess_extension(content_type.split(";")[0].strip()) or ""
    if content_type.startswith("audio/ogg"):
        suffix = ".ogg"
    elif content_type == "audio/mpeg":
        suffix = ".mp3"
    out = TMP_DIR / f"{_safe_stem(message_sid)}_{index}{suffix}"
    with requests.get(
        media_url,
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


def _forward_audio_to_voice_app(payload: dict, media_path: Path) -> dict:
    caller = str(payload.get("From") or "").replace("whatsapp:", "")
    message_sid = str(payload.get("MessageSid") or "")
    body = str(payload.get("Body") or "").strip()
    profile_name = str(payload.get("ProfileName") or "").strip()

    data = {
        "contact_info": caller,
        "account_or_reference": message_sid,
        "telephony_source_number": str(payload.get("To") or "").replace("whatsapp:", ""),
        "telephony_call_mode": "whatsapp_voice_note",
        "telephony_provider": "twilio_whatsapp",
    }
    if profile_name:
        data["caller_name_hint"] = profile_name
    if body:
        data["accompanying_text"] = body
    data = {k: v for k, v in data.items() if v}

    mime = mimetypes.guess_type(media_path.name)[0] or "application/octet-stream"
    with media_path.open("rb") as f:
        files = {"file": (media_path.name, f, mime)}
        resp = requests.post(VOICE_APP_UPLOAD_URL, data=data, files=files, timeout=FORWARD_TIMEOUT)
    resp.raise_for_status()
    try:
        return resp.json()
    except ValueError:
        return {"status": "ok", "raw": resp.text}


def _persist_media(media_path: Path, message_sid: str, index: int) -> Path:
    dest = MEDIA_DIR / f"{_safe_stem(message_sid)}_{index}{media_path.suffix}"
    media_path.replace(dest)
    return dest


def _twiml(text: str | None) -> Response:
    twiml = MessagingResponse()
    if text and not SILENT_REPLY:
        twiml.message(text)
    return Response(str(twiml), mimetype="application/xml")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/health", methods=["GET"])
def health() -> tuple[Response, int]:
    return jsonify({
        "status": "ok",
        "twilio_configured": bool(_twilio),
        "signature_validation": VALIDATE_SIGNATURE,
        "db_connected": _pool is not None,
    }), 200


@app.route("/webhooks/inbound", methods=["POST"])
def inbound() -> Response:
    if not _signature_valid():
        logger.warning("Rejected inbound webhook: invalid Twilio signature")
        return Response("invalid signature", status=403)

    payload = request.form.to_dict(flat=True)
    _save_event(payload, "inbound")

    num_media = int(payload.get("NumMedia") or 0)
    message_sid = str(payload.get("MessageSid") or "msg")
    from_ = payload.get("From", "")
    body = (payload.get("Body") or "").strip()
    contact_phone = from_.replace("whatsapp:", "")
    contact_name = payload.get("ProfileName") or None
    message_type = _infer_message_type(num_media, payload)

    logger.info("Inbound WhatsApp from %s — type=%s body=%r media=%d", from_, message_type, body[:80], num_media)

    # Persist conversation + message to DB (non-fatal if DB is down)
    db_message_id: int | None = None
    try:
        with _Db() as db:
            if db.available:
                conv_id = db.upsert_conversation(contact_phone, contact_name)
                db_message_id = db.insert_message(
                    conv_id, message_sid, "inbound", "received", message_type,
                    body or None, payload,
                )
    except Exception as exc:
        logger.warning("DB write failed for inbound %s: %s", message_sid, exc)

    if num_media == 0:
        return _twiml(AUTO_ACK_TEXT if body else None)

    audio_results: list[dict] = []
    archived: list[str] = []
    forward_error: str | None = None

    for i in range(num_media):
        media_url = payload.get(f"MediaUrl{i}")
        content_type = payload.get(f"MediaContentType{i}", "")
        if not media_url:
            continue

        try:
            tmp_path = _download_media(media_url, message_sid, i, content_type)
        except Exception as exc:
            logger.exception("Failed to download media %d", i)
            forward_error = str(exc)
            continue

        is_audio = content_type.startswith("audio/")
        dest: Path | None = None
        voice_app_result: dict | None = None

        if is_audio:
            try:
                voice_app_result = _forward_audio_to_voice_app(payload, tmp_path)
                audio_results.append({"index": i, "voice_app": voice_app_result})
            except Exception as exc:
                logger.exception("Failed forwarding audio %d to voice-app", i)
                forward_error = str(exc)
            if tmp_path.exists():
                dest = _persist_media(tmp_path, message_sid, i)
                archived.append(str(dest))
        else:
            dest = _persist_media(tmp_path, message_sid, i)
            archived.append(str(dest))

        # Persist media row
        if db_message_id is not None:
            try:
                file_size = dest.stat().st_size if dest and dest.exists() else None
                local_path = str(dest) if dest else None
                with _Db() as db:
                    if db.available:
                        db.insert_media(db_message_id, i, media_url, content_type, local_path, file_size)
            except Exception as exc:
                logger.warning("DB media write failed for %s[%d]: %s", message_sid, i, exc)

        # If voice-app returned an incident_form_id, link it immediately
        if voice_app_result and db_message_id is not None:
            form_id = (
                voice_app_result.get("incident_form_id")
                or voice_app_result.get("form_id")
                or voice_app_result.get("id")
            )
            if isinstance(form_id, int):
                try:
                    with _Db() as db:
                        if db.available:
                            db.set_incident_form(db_message_id, form_id)
                except Exception as exc:
                    logger.warning("DB set_incident_form failed: %s", exc)

    logger.info(
        "Processed inbound %s — audio_forwarded=%d archived=%d error=%s",
        message_sid, len(audio_results), len(archived), forward_error,
    )

    if audio_results:
        reply = AUTO_ACK_VOICE
    elif forward_error and not archived:
        reply = "Sorry — we couldn't process that attachment. Please try again."
    else:
        reply = AUTO_ACK_TEXT
    return _twiml(reply)


@app.route("/webhooks/status", methods=["POST"])
def status_callback() -> Response:
    if not _signature_valid():
        return Response("invalid signature", status=403)
    payload = request.form.to_dict(flat=True)
    _save_event(payload, "status")

    sid = payload.get("MessageSid")
    status = payload.get("MessageStatus")
    logger.info("Status update — sid=%s status=%s error=%s", sid, status, payload.get("ErrorCode"))

    if sid and status:
        try:
            with _Db() as db:
                if db.available:
                    db.update_status(sid, status)
        except Exception as exc:
            logger.warning("DB status update failed for %s: %s", sid, exc)

    return Response(status=204)


@app.route("/send", methods=["POST"])
def send() -> tuple[Response, int]:
    """Outbound send. JSON body: {to, body?, media_url?}."""
    if _twilio is None:
        return jsonify({"error": "twilio not configured — set TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN"}), 503
    if not TWILIO_WHATSAPP_FROM:
        return jsonify({"error": "TWILIO_WHATSAPP_FROM not configured"}), 503

    data = request.get_json(silent=True) or {}
    to = str(data.get("to") or "").strip()
    body = data.get("body")
    media_url = data.get("media_url")

    if not to:
        return jsonify({"error": "`to` is required"}), 400
    if not body and not media_url:
        return jsonify({"error": "at least one of `body` or `media_url` is required"}), 400
    if not to.startswith("whatsapp:"):
        to = f"whatsapp:{to}"
    if media_url:
        scheme = urlparse(media_url).scheme
        if scheme not in ("http", "https"):
            return jsonify({"error": "media_url must be http(s)"}), 400

    try:
        kwargs: dict = {"from_": TWILIO_WHATSAPP_FROM, "to": to}
        if body:
            kwargs["body"] = str(body)
        if media_url:
            kwargs["media_url"] = [media_url] if isinstance(media_url, str) else list(media_url)
        msg = _twilio.messages.create(**kwargs)
    except Exception as exc:
        logger.exception("Twilio send failed")
        return jsonify({"error": str(exc)}), 502

    # Persist outbound message to DB
    contact_phone = to.replace("whatsapp:", "")
    try:
        with _Db() as db:
            if db.available:
                conv_id = db.upsert_conversation(contact_phone, None)
                db.insert_message(
                    conv_id, msg.sid, "outbound", msg.status,
                    "text" if not media_url else "document",
                    str(body) if body else None,
                    {"to": to, "body": body, "media_url": media_url},
                )
    except Exception as exc:
        logger.warning("DB write failed for outbound %s: %s", msg.sid, exc)

    return jsonify({"sid": msg.sid, "status": msg.status, "to": to}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5011, debug=True)
