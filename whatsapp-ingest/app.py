"""
WhatsApp Ingest – Twilio WhatsApp prototype.

Receives inbound WhatsApp messages (text, media, voice notes) from the
Twilio sandbox or a production WhatsApp sender, forwards audio media to
the existing voice-app /upload pipeline (so transcription + form-fill
runs unchanged), and exposes /send for outbound text + media replies.

Mirrors the shape of telephony-ingest so ops/runtime are consistent.
"""

import json
import logging
import mimetypes
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

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

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_WHATSAPP_FROM = os.getenv("TWILIO_WHATSAPP_FROM", "")  # e.g. whatsapp:+14155238886
VALIDATE_SIGNATURE = os.getenv("TWILIO_VALIDATE_SIGNATURE", "true").lower() == "true"
PUBLIC_BASE_URL = os.getenv("WHATSAPP_PUBLIC_BASE_URL", "")  # used only for signature validation behind a proxy

VOICE_APP_UPLOAD_URL = os.getenv("VOICE_APP_UPLOAD_URL", "http://voice-app:5000/upload")
FORWARD_TIMEOUT = int(os.getenv("VOICE_APP_FORWARD_TIMEOUT", "900"))
MEDIA_DOWNLOAD_TIMEOUT = int(os.getenv("MEDIA_DOWNLOAD_TIMEOUT", "120"))

EVENTS_DIR = Path(os.getenv("WHATSAPP_EVENTS_DIR", "/data/shared/whatsapp-events"))
MEDIA_DIR = Path(os.getenv("WHATSAPP_MEDIA_DIR", "/data/shared/whatsapp-media"))
TMP_DIR = Path(os.getenv("WHATSAPP_TMP_DIR", "/tmp/whatsapp"))

AUTO_ACK_TEXT = os.getenv("WHATSAPP_AUTO_ACK_TEXT", "Got it — processing your message.")
AUTO_ACK_VOICE = os.getenv("WHATSAPP_AUTO_ACK_VOICE", "Got your voice note — transcribing now.")
SILENT_REPLY = os.getenv("WHATSAPP_SILENT_REPLY", "false").lower() == "true"

EVENTS_DIR.mkdir(parents=True, exist_ok=True)
MEDIA_DIR.mkdir(parents=True, exist_ok=True)
TMP_DIR.mkdir(parents=True, exist_ok=True)

_validator = RequestValidator(TWILIO_AUTH_TOKEN) if TWILIO_AUTH_TOKEN else None
_twilio: TwilioClient | None = None
if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
    _twilio = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)


def _safe_stem(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in value)
    return cleaned[:120] if cleaned else "msg"


def _request_url_for_signature() -> str:
    # When sitting behind ngrok / a reverse proxy, request.url reflects the
    # internal scheme/host. Twilio signs the *public* URL, so allow an override.
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
    # Twilio signs the form-encoded body params for POSTs.
    params = request.form.to_dict(flat=True)
    return _validator.validate(_request_url_for_signature(), params, signature)


def _save_event(payload: dict, kind: str) -> Path:
    message_sid = payload.get("MessageSid") or payload.get("SmsMessageSid") or datetime.now(timezone.utc).isoformat()
    out = EVENTS_DIR / f"{kind}_{_safe_stem(str(message_sid))}.json"
    with out.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return out


def _download_media(media_url: str, message_sid: str, index: int, content_type: str) -> Path:
    suffix = mimetypes.guess_extension(content_type.split(";")[0].strip()) or ""
    # WhatsApp voice notes arrive as audio/ogg; guess_extension returns .ogx — prefer .ogg.
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
    # Keep an archive copy of every inbound attachment for the dashboard / audit.
    dest = MEDIA_DIR / f"{_safe_stem(message_sid)}_{index}{media_path.suffix}"
    media_path.replace(dest)
    return dest


def _twiml(text: str | None) -> Response:
    twiml = MessagingResponse()
    if text and not SILENT_REPLY:
        twiml.message(text)
    return Response(str(twiml), mimetype="application/xml")


@app.route("/health", methods=["GET"])
def health() -> tuple[Response, int]:
    return jsonify({
        "status": "ok",
        "twilio_configured": bool(_twilio),
        "signature_validation": VALIDATE_SIGNATURE,
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

    logger.info("Inbound WhatsApp from %s — body=%r media=%d", from_, body[:80], num_media)

    if num_media == 0:
        # Plain text message — just ack for now. Hook into your own logic here.
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
        if is_audio:
            try:
                result = _forward_audio_to_voice_app(payload, tmp_path)
                audio_results.append({"index": i, "voice_app": result})
            except Exception as exc:
                logger.exception("Failed forwarding audio %d to voice-app", i)
                forward_error = str(exc)
            finally:
                # Voice-app keeps its own copy; archive ours too for traceability.
                if tmp_path.exists():
                    dest = _persist_media(tmp_path, message_sid, i)
                    archived.append(str(dest))
        else:
            dest = _persist_media(tmp_path, message_sid, i)
            archived.append(str(dest))

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
    logger.info(
        "Status update — sid=%s status=%s error=%s",
        payload.get("MessageSid"), payload.get("MessageStatus"), payload.get("ErrorCode"),
    )
    return Response(status=204)


@app.route("/send", methods=["POST"])
def send() -> tuple[Response, int]:
    """Outbound send. JSON body: {to, body?, media_url?}.

    `to` may be a bare E.164 number ("+15551234567") or already prefixed
    ("whatsapp:+15551234567"). At least one of body / media_url is required.
    """
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
        # Twilio requires a publicly fetchable URL — sanity-check the scheme.
        scheme = urlparse(media_url).scheme
        if scheme not in ("http", "https"):
            return jsonify({"error": "media_url must be http(s)"}), 400

    try:
        kwargs = {"from_": TWILIO_WHATSAPP_FROM, "to": to}
        if body:
            kwargs["body"] = str(body)
        if media_url:
            kwargs["media_url"] = [media_url] if isinstance(media_url, str) else list(media_url)
        msg = _twilio.messages.create(**kwargs)
        return jsonify({"sid": msg.sid, "status": msg.status, "to": to}), 200
    except Exception as exc:
        logger.exception("Twilio send failed")
        return jsonify({"error": str(exc)}), 502


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5011, debug=True)
