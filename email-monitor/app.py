"""
Email Monitor Service
=====================
Monitors Outlook inbox, classifies emails, and sends notifications.
Lightweight - no database storage, just real-time classification and notification.
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from collections import deque
import threading
import time
import base64
import tempfile
from pathlib import Path

from flask import Flask, jsonify, render_template, request
import requests
from dotenv import load_dotenv

from email_utils import is_support_recipient, strip_html
from graph_auth import (
    GraphAuthError,
    auth_mode,
    authorization_headers,
    inbox_messages_url,
    is_configured,
    message_attachments_url,
    uses_graph,
    verify_mailbox_access,
)
from processed_store import ProcessedEmailStore

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configuration
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
OLLAMA_CONNECT_TIMEOUT = int(os.getenv("OLLAMA_CONNECT_TIMEOUT", "3"))
OLLAMA_READ_TIMEOUT = int(os.getenv("OLLAMA_READ_TIMEOUT", "120"))
VOICE_APP_URL = os.getenv("VOICE_APP_URL", "http://voice-app:5000")
TRANSCRIBER_URL = os.getenv("TRANSCRIBER_URL", "http://transcriber:9000/transcribe")

# Attachment storage and processing
ATTACHMENTS_STORAGE = os.getenv("ATTACHMENTS_STORAGE", "/storage/uploads")
MAX_ATTACHMENT_SIZE_MB = int(os.getenv("MAX_ATTACHMENT_SIZE_MB", "10"))
ATTACHMENT_TYPES_TO_PROCESS = {"audio", "video", "document", "pdf", "image", "text"}

# In-memory notification queue (last 20 notifications)
notification_queue = deque(maxlen=20)
queue_lock = threading.Lock()

GRAPH_TOKEN = None

# Persist processed message IDs across restarts (ISR-241)
processed_store = ProcessedEmailStore()

# ---------------------------------------------------------------------------
# Attachment Processing Functions
# ---------------------------------------------------------------------------

def categorize_attachment(content_type: str) -> str:
    """Categorize attachment by MIME type."""
    if content_type.startswith("video/"):
        return "video"
    elif content_type.startswith("audio/"):
        return "audio"
    elif content_type.startswith("image/"):
        return "image"
    elif "pdf" in content_type.lower():
        return "pdf"
    elif "word" in content_type.lower() or "document" in content_type.lower() or "msword" in content_type.lower():
        return "document"
    elif "excel" in content_type.lower() or "spreadsheet" in content_type.lower():
        return "spreadsheet"
    elif content_type.startswith("text/"):
        return "text"
    else:
        return "other"


def extract_text_from_pdf(file_path: str) -> Optional[str]:
    """Extract text from PDF file."""
    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(file_path)
        text = ""
        for page in reader.pages[:10]:  # Limit to first 10 pages
            text += page.extract_text() + "\n"
        return text[:5000]  # Return first 5000 chars
    except Exception as e:
        logger.error(f"PDF extraction failed: {e}")
        return None


def extract_text_from_docx(file_path: str) -> Optional[str]:
    """Extract text from Word document."""
    try:
        from docx import Document
        doc = Document(file_path)
        text = ""
        for paragraph in doc.paragraphs[:100]:  # Limit to first 100 paragraphs
            text += paragraph.text + "\n"
        return text[:5000]
    except Exception as e:
        logger.error(f"DOCX extraction failed: {e}")
        return None


def extract_text_from_image(file_path: str) -> Optional[str]:
    """Skip image OCR. Images are stored for manual review."""
    return None


def extract_audio_from_video(video_path: str) -> Optional[str]:
    """Extract audio from video file and save as temporary WAV."""
    try:
        import subprocess
        audio_path = video_path.replace(Path(video_path).suffix, ".wav")
        
        # Use ffmpeg to extract audio
        cmd = ["ffmpeg", "-i", video_path, "-q:a", "9", "-n", audio_path]
        result = subprocess.run(cmd, capture_output=True, timeout=60)
        
        if result.returncode == 0 and os.path.exists(audio_path):
            logger.info(f"Extracted audio from video: {audio_path}")
            return audio_path
        else:
            logger.error(f"FFmpeg extraction failed: {result.stderr.decode()}")
            return None
    except Exception as e:
        logger.warning(f"Video audio extraction failed: {e}")
        return None


def transcribe_audio(file_path: str) -> Optional[Dict]:
    """Send audio to transcriber service for transcription with diarization."""
    try:
        with open(file_path, "rb") as f:
            files = {"file": (Path(file_path).name, f)}
            response = requests.post(
                TRANSCRIBER_URL,
                files=files,
                data={"num_speakers": 2, "diarize": "true"},
                timeout=300
            )
        
        if response.status_code == 200:
            result = response.json()
            logger.info(f"Transcription successful: {result['word_count']} words")
            return result
        else:
            logger.error(f"Transcriber error {response.status_code}: {response.text}")
            return None
    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        return None


def process_attachment(attachment_info: Dict, message_id: str) -> Optional[Dict]:
    """Process attachment and extract content for analysis."""
    try:
        filename = attachment_info.get("name", "unknown")
        content_type = attachment_info.get("contentType", "")
        content_bytes_b64 = attachment_info.get("contentBytes", "")
        file_type = categorize_attachment(content_type)
        
        logger.error(f"CONTENT BYTES EXISTS: {bool(content_bytes_b64)}")
        
        attachment_id = attachment_info.get("id", "")
        
        # Decode base64 content
        try:
            content_bytes = base64.b64decode(content_bytes_b64)
        except Exception as e:
            logger.error(f"Failed to decode attachment {filename}: {e}")
            return None
        
        # Create type-specific directory
        type_dir = os.path.join(ATTACHMENTS_STORAGE, file_type)
        os.makedirs(type_dir, exist_ok=True)

        short_id = message_id[:12]
        safe_filename = f"{short_id}_{filename}"
        file_path = os.path.join(type_dir, safe_filename)
        
        if file_type not in ATTACHMENT_TYPES_TO_PROCESS:
            logger.warning(f"Skipping unsupported attachment type: {file_type}")
            return None
        
        try:
            with open(file_path, "wb") as f:
                f.write(content_bytes)
            logger.info(f"Saved attachment: {filename} ({len(content_bytes)} bytes)")
        except Exception as e:
            logger.error(f"Failed to save attachment: {e}")
            return None
        
        # Extract content based on file type
        extracted_content = None
        transcript = None
        
        if file_type == "pdf":
            extracted_content = extract_text_from_pdf(file_path)
        
        elif file_type == "document":
            extracted_content = extract_text_from_docx(file_path)
        
        elif file_type == "image":
            extracted_content = extract_text_from_image(file_path)
        
        elif file_type == "audio":
            transcript = transcribe_audio(file_path)
        
        elif file_type == "video":
            # Extract audio from video first
            audio_path = extract_audio_from_video(file_path)
            if audio_path:
                transcript = transcribe_audio(audio_path)
        
        elif file_type == "text":
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    extracted_content = f.read()[:5000]
            except Exception as e:
                logger.error(f"Failed to read text file: {e}")
        
        result = {
            "filename": filename,
            "type": file_type,
            "size": len(content_bytes),
            "content_type": content_type,
            "file_path": file_path,
            "extracted_text": extracted_content,
            "transcript": transcript
        }
        
        return result
    
    except Exception as e:
        logger.error(f"Attachment processing failed: {e}", exc_info=True)
        return None


def get_email_attachments(token: str, message_id: str) -> List[Dict]:
    """Fetch and process all attachments for an email."""
    try:
        headers = authorization_headers(token)
        url = message_attachments_url(message_id)
        
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        attachments_meta = data.get("value", [])
        logger.error(f"RAW ATTACHMENTS: {attachments_meta}")
        
        logger.info(f"Found {len(attachments_meta)} attachments for message {message_id}")
        
        processed_attachments = []
        
        for attachment in attachments_meta:
            attachment_id = attachment.get("id")
            filename = attachment.get("name")
            size_bytes = attachment.get("size", 0)
            content_type = attachment.get("contentType", "")
            
            # Check size limit
            size_mb = size_bytes / (1024 * 1024)
            if size_mb > MAX_ATTACHMENT_SIZE_MB:
                logger.warning(
                    f"Unsupported attachment size: {filename} "
                    f"({size_mb:.2f}MB > {MAX_ATTACHMENT_SIZE_MB}MB). "
                    f"Skipping attachment."
                )
                continue
            
            logger.info(f"Downloading: {filename} ({size_mb:.1f}MB) - {content_type}")
            
            # Download attachment content
            try:
                url_download = f"https://graph.microsoft.com/v1.0/me/messages/{message_id}/attachments/{attachment_id}"
                response_download = requests.get(url_download, headers=headers, timeout=30)
                response_download.raise_for_status()
                
                attachment_full = response_download.json()
                logger.error(f"ATTACHMENT FULL: {attachment_full}")

                logger.info(f"Attachment keys: {attachment_full.keys()}")
                
                # Only process file attachments with content
                if attachment_full.get("@odata.type") == "#microsoft.graph.fileAttachment":
                    attachment_full["id"] = attachment_id  # Ensure ID is included
                    processed = process_attachment(attachment_full, message_id)
                    
                    logger.error(f"PROCESSING ATTACHMENT: {filename}")
                    if processed:
                        processed_attachments.append(processed)
                
            except Exception as e:
                logger.error(f"Failed to download attachment {filename}: {e}")
                continue
        
        return processed_attachments
    
    except Exception as e:
        logger.error(f"Failed to fetch attachments: {e}")
        return []


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.route("/", methods=["GET"])
def index_dashboard():
    return render_template("index.html")


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint."""
    mode = None
    if is_configured():
        try:
            mode = auth_mode()
        except GraphAuthError:
            mode = "invalid"
    return jsonify(
        {
            "status": "ok",
            "service": "email-monitor",
            "auth_mode": mode,
            "email_configured": is_configured(),
        }
    ), 200


@app.route("/health/graph", methods=["GET"])
def health_graph():
    try:
        mode = auth_mode()
    except GraphAuthError as exc:
        return jsonify({"status": "error", "message": str(exc)}), 503

    if mode == "imap":
        return jsonify(
            {
                "status": "skipped",
                "message": "GRAPH_AUTH_MODE=imap — use GET /health/imap instead.",
            }
        ), 200

    if not is_configured():
        return jsonify(
            {
                "status": "not_configured",
                "message": "See docs/EMAIL_INGEST_SETUP.md or GRAPH_EMAIL_READ.md.",
            }
        ), 503

    try:
        result = verify_mailbox_access()
        status_code = 200 if result.get("ok") else 502
        return jsonify({"status": "ok" if result.get("ok") else "error", **result}), status_code
    except GraphAuthError as exc:
        return jsonify({"status": "error", "message": str(exc)}), 503
    except Exception as exc:
        logger.exception("Graph health check failed")
        return jsonify({"status": "error", "message": str(exc)}), 502


@app.route("/health/imap", methods=["GET"])
def health_imap():
    if auth_mode() != "imap":
        return jsonify(
            {
                "status": "skipped",
                "message": "Set GRAPH_AUTH_MODE=imap for this check.",
            }
        ), 200

    from imap_client import ImapConfigError, is_configured as imap_ok, verify_access

    if not imap_ok():
        return jsonify(
            {
                "status": "not_configured",
                "message": "Set OUTLOOK_IMAP_USER and OUTLOOK_IMAP_PASSWORD. See docs/EMAIL_INGEST_SETUP.md.",
            }
        ), 503

    try:
        result = verify_access()
        status_code = 200 if result.get("ok") else 502
        return jsonify({"status": "ok" if result.get("ok") else "error", **result}), status_code
    except ImapConfigError as exc:
        return jsonify({"status": "error", "message": str(exc)}), 503
    except Exception as exc:
        logger.exception("IMAP health check failed")
        return jsonify({"status": "error", "message": str(exc)}), 502


@app.route("/notifications", methods=["GET"])
def get_notifications():
    """Get all notifications in the queue."""
    with queue_lock:
        notifications = list(notification_queue)
    return jsonify({"notifications": notifications}), 200


@app.route("/sync", methods=["POST"])
def trigger_sync():
    """Run one inbox sync immediately (demo helper)."""
    if not is_configured():
        return jsonify({"status": "error", "message": "Email ingest not configured."}), 503
    try:
        sync_emails()
        return jsonify({"status": "ok", "message": "Sync completed — check logs and Mailpit."}), 200
    except Exception as exc:
        logger.exception("Manual sync failed")
        return jsonify({"status": "error", "message": str(exc)}), 502


@app.route("/notifications/clear", methods=["POST"])
def clear_notifications():
    """Clear all notifications."""
    with queue_lock:
        notification_queue.clear()
    return jsonify({"status": "cleared"}), 200


@app.route("/attachments/<attachment_type>", methods=["GET"])
def get_attachments_by_type(attachment_type: str):
    """Get attachments of a specific type from recent emails.
    
    Parameters:
        attachment_type: 'audio', 'video', 'document', 'pdf', 'image', etc.
    """
    attachment_type = attachment_type.lower()
    
    with queue_lock:
        notifications = list(notification_queue)
    
    matching_attachments = []
    
    for notification in notifications:
        if "attachments" in notification:
            for attachment in notification["attachments"]:
                if attachment.get("type") == attachment_type:
                    attachment_with_email = {
                        **attachment,
                        "from_email": notification.get("sender"),
                        "email_subject": notification.get("subject")
                    }
                    matching_attachments.append(attachment_with_email)
    
    return jsonify({
        "type": attachment_type,
        "count": len(matching_attachments),
        "attachments": matching_attachments
    }), 200


@app.route("/attachments/file/<filename>", methods=["GET"])
def get_attachment_file(filename: str):
    """Serve attachment file (image, video, audio, etc.)."""
    from flask import send_from_directory
    
    try:
        return send_from_directory(ATTACHMENTS_STORAGE, filename, as_attachment=False)
    except Exception as e:
        logger.error(f"Failed to serve file {filename}: {e}")
        return jsonify({"error": "File not found or access denied"}), 404


# ---------------------------------------------------------------------------
# Email Processing
# ---------------------------------------------------------------------------

def get_graph_token() -> str:
    """Acquire a Microsoft Graph access token (ISR-303)."""
    from graph_auth import acquire_token

    return acquire_token()


def _filter_new_imap_messages(items: list) -> list:
    """Apply dedupe + support filter to IMAP messages (ISR-241)."""
    emails = []
    for item in items:
        message_id = str(item.get("message_id") or item.get("key") or "")
        if not message_id or processed_store.contains(message_id):
            continue
        processed_store.mark_processed(message_id)
        logger.info(
            "New email detected message_id=%s sender=%s subject=%s",
            message_id,
            item.get("sender"),
            str(item.get("subject", ""))[:80],
        )
        emails.append(item)
    return emails


def fetch_inbox_emails(token: str | None = None) -> list:
    """Fetch new messages via IMAP or Graph depending on GRAPH_AUTH_MODE."""
    if auth_mode() == "imap":
        from imap_client import fetch_unseen_emails

        return _filter_new_imap_messages(fetch_unseen_emails(limit=10))

    if token is None:
        token = get_graph_token()
    return fetch_emails_from_graph(token)


def fetch_emails_from_graph(token: str) -> list:
    """Fetch new inbox messages via Microsoft Graph (ISR-241)."""

    headers = authorization_headers(token)
    url = inbox_messages_url(top=10)

    response = requests.get(url, headers=headers, timeout=30)
    logger.info("Graph inbox fetch status: %s", response.status_code)
    if response.status_code >= 400:
        logger.error("Graph inbox fetch failed: %s", response.text[:500])
    response.raise_for_status()

    messages = response.json().get("value", [])
    emails = []

    for msg in messages:
        message_id = msg.get("id", "")
        if not message_id or processed_store.contains(message_id):
            if message_id:
                logger.debug("Skipped duplicate message_id=%s", message_id)
            continue

        to_addresses = [
            (r.get("emailAddress") or {}).get("address", "")
            for r in msg.get("toRecipients") or []
        ]
        cc_addresses = [
            (r.get("emailAddress") or {}).get("address", "")
            for r in msg.get("ccRecipients") or []
        ]
        if not is_support_recipient(to_addresses, cc_addresses):
            logger.info(
                "Skipped non-support recipient message_id=%s to=%s",
                message_id,
                to_addresses,
            )
            processed_store.mark_processed(message_id)
            continue

        subject = msg.get("subject", "")
        sender = (msg.get("from", {}) or {}).get("emailAddress", {}).get("address", "")
        body_obj = msg.get("body") or {}
        if body_obj.get("contentType") == "html":
            body = strip_html(body_obj.get("content") or "")
        else:
            body = (body_obj.get("content") or msg.get("bodyPreview") or "")
        received_at = msg.get("receivedDateTime", "")
        has_attachments = msg.get("hasAttachments", False)

        email_obj = {
            "sender": sender,
            "subject": subject,
            "body": body,
            "received_at": received_at,
            "message_id": message_id,
            "attachments": [],
        }

        if has_attachments and message_id:
            attachments = get_email_attachments(token, message_id)
            email_obj["attachments"] = attachments
            logger.info("Fetched %d attachments for message_id=%s", len(attachments), message_id)

        processed_store.mark_processed(message_id)
        logger.info(
            "New email detected message_id=%s sender=%s subject=%s",
            message_id,
            sender,
            subject[:80],
        )
        emails.append(email_obj)

    return emails


def forward_to_voice_app(email_data: dict) -> None:
    """POST detected email to voice-app; failures must not crash sync loop (ISR-242)."""
    payload = {
        "subject": email_data.get("subject", ""),
        "body": email_data.get("body", ""),
        "sender": email_data.get("sender", ""),
        "message_id": email_data.get("message_id"),
        "received_at": email_data.get("received_at"),
    }
    try:
        response = requests.post(
            f"{VOICE_APP_URL.rstrip('/')}/ingest/email",
            json=payload,
            timeout=120,
        )
        if response.status_code >= 400:
            logger.error(
                "voice-app ingest failed message_id=%s status=%s body=%s",
                email_data.get("message_id"),
                response.status_code,
                response.text[:300],
            )
            return
        logger.info(
            "Forwarded message_id=%s to voice-app ingest",
            email_data.get("message_id"),
        )
    except Exception as exc:
        logger.error(
            "Pipeline forward failed message_id=%s: %s",
            email_data.get("message_id"),
            exc,
        )


def decode_header_str(header: str) -> str:
    """Decode email header."""
    if not header:
        return ""
    from email.header import decode_header
    try:
        decoded_parts = []
        for part, encoding in decode_header(header):
            if isinstance(part, bytes):
                encoding = encoding or "utf-8"
                decoded_parts.append(part.decode(encoding, errors="replace"))
            else:
                decoded_parts.append(str(part))
        return "".join(decoded_parts)
    except:
        return str(header)


def extract_body(msg) -> str:
    """Extract text body from email."""
    import re
    body = ""

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            if content_type == "text/plain":
                try:
                    body = part.get_payload(decode=True).decode("utf-8", errors="replace")
                    break
                except:
                    continue
            elif content_type == "text/html" and not body:
                try:
                    html = part.get_payload(decode=True).decode("utf-8", errors="replace")
                    body = re.sub(r"<[^>]+>", "", html)
                    break
                except:
                    continue
    else:
        try:
            body = msg.get_payload(decode=True).decode("utf-8", errors="replace")
        except:
            body = msg.get_payload()

    return body[:500]  # Truncate to 500 chars


def classify_email(subject: str, body: str, attachments_info: str = "") -> dict:
    """Classify email as service-related using Ollama, including attachment content."""
    try:
        # Combine email and attachment content for analysis
        combined_content = f"Subject: {subject}\n\nBody: {body}"
        
        if attachments_info:
            combined_content += f"\n\nAttachment Content:\n{attachments_info}"
        
        prompt = f"""Determine if this email is about a SERVICE CALL (machine problems, equipment issues, maintenance, technical support).

{combined_content[:2000]}

Respond with ONLY a JSON object:
{{"is_service_related": true/false, "reason": "brief reason"}}

Examples of SERVICE: machine breakdown, equipment repair, technical issue, system error
Examples of NON-SERVICE: newsletter, marketing, thank you, appointment
"""

        response = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "temperature": 0.3,
            },
            timeout=(OLLAMA_CONNECT_TIMEOUT, OLLAMA_READ_TIMEOUT),
        )
        response.raise_for_status()

        result = response.json()
        response_text = result.get("response", "")

        # Extract JSON from response
        import json
        json_start = response_text.find("{")
        json_end = response_text.rfind("}") + 1
        if json_start != -1 and json_end > json_start:
            parsed = json.loads(response_text[json_start:json_end])
            return {
                "is_service_related": parsed.get("is_service_related", False),
                "reason": parsed.get("reason", ""),
            }
        else:
            return {"is_service_related": False, "reason": "Parse error"}

    except Exception as e:
        logger.error(f"Classification failed: {e}")
        return {"is_service_related": False, "reason": "Error"}


def add_notification(notification: dict):
    """Add notification to queue."""
    with queue_lock:
        notification["timestamp"] = datetime.utcnow().isoformat()
        notification_queue.append(notification)
        logger.info(f"Added notification: {notification['type']}")


def sync_emails():
    logger.info("Starting email sync...")

    try:
        global GRAPH_TOKEN

        if uses_graph() and not GRAPH_TOKEN:
            GRAPH_TOKEN = get_graph_token()

        emails = fetch_inbox_emails(GRAPH_TOKEN)

        logger.info(f"Processing {len(emails)} emails")

        for email_data in emails:
            # Build attachment content summary for analysis
            attachments_text = ""
            attachments_summary = []
            
            if email_data.get("attachments"):
                for attachment in email_data["attachments"]:
                    file_type = attachment.get("type", "unknown")
                    filename = attachment.get("filename", "unknown")
                    
                    summary = {
                        "name": filename,
                        "type": file_type,
                        "size_mb": round(attachment.get("size", 0) / (1024 * 1024), 2),
                        "file_url": f"http://email-monitor:5003/attachments/file/{filename}"  # URL to view/download
                    }
                    
                    # Include extracted content in the analysis text
                    if attachment.get("extracted_text"):
                        attachments_text += f"\n[{file_type}: {filename}]\n{attachment['extracted_text'][:1000]}\n"
                        summary["has_content"] = True
                    
                    if attachment.get("transcript"):
                        transcript_text = attachment["transcript"].get("text", "")
                        attachments_text += f"\n[Transcript from {filename}]\n{transcript_text[:1000]}\n"
                        summary["transcript_words"] = attachment["transcript"].get("word_count", 0)
                        summary["speakers"] = attachment["transcript"].get("speakers_detected", 0)
                        summary["has_transcript"] = True
                    
                    attachments_summary.append(summary)
            
            # Classify email with attachment context
            classification = classify_email(
                email_data["subject"],
                email_data["body"],
                attachments_text
            )

            notification = {
                "type": "service" if classification["is_service_related"] else "non_service",
                "sender": email_data["sender"],
                "subject": email_data["subject"],
                "body_preview": email_data["body"][:200],
                "reason": classification["reason"],
            }
            
            # Add attachment info to notification
            if attachments_summary:
                notification["attachments"] = attachments_summary
                notification["attachment_count"] = len(attachments_summary)

            add_notification(notification)

            # Forward every newly detected email to voice-app pipeline (ISR-242)
            forward_to_voice_app(email_data)

        logger.info("Email sync completed")

    except Exception as e:
        logger.error(f"Sync error: {e}", exc_info=True)


def background_sync():
    """Background thread that syncs emails periodically."""
    while True:
        try:
            sync_emails()
            time.sleep(300)  # Check every 5 minutes
        except Exception as e:
            logger.error(f"Background sync error: {e}")
            time.sleep(60)  # Retry after 1 minute on error


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------

# Start background sync thread on module load
def init_background_sync():
    """Initialize background sync thread."""
    logger.info("Starting email-monitor service")
    sync_thread = threading.Thread(target=background_sync, daemon=True)
    sync_thread.start()
    logger.info("Background sync thread started")


GRAPH_TOKEN = None
_background_sync_enabled = os.getenv("EMAIL_ENABLE_BACKGROUND_SYNC", "true").strip().lower() in (
    "true",
    "1",
    "yes",
    "on",
)

if is_configured():
    try:
        if uses_graph():
            GRAPH_TOKEN = get_graph_token()
            logger.info("Microsoft Graph ready (mode=%s).", auth_mode())
        else:
            from imap_client import imap_user

            logger.info("Outlook IMAP ready for mailbox=%s.", imap_user())
        if _background_sync_enabled:
            init_background_sync()
        else:
            logger.info(
                "Background email sync disabled (EMAIL_ENABLE_BACKGROUND_SYNC=false)."
            )
    except Exception as e:
        logger.error("Failed to initialize email ingest or background sync: %s", e)
else:
    logger.warning(
        "Email ingest not configured. See docs/EMAIL_INGEST_SETUP.md."
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5003, debug=False, threaded=True)
