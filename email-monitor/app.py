"""
Email Monitor Service
=====================
Monitors Outlook inbox, classifies emails, and sends notifications.
Lightweight - no database storage, just real-time classification and notification.
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Optional
from collections import deque
import threading
import time

from flask import Flask, jsonify, request
import requests
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configuration
GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS", "fjodsmorod@gmail.com")
GMAIL_PASSWORD = os.getenv("GMAIL_PASSWORD", "fsuf ijxk wmhi drix")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
VOICE_APP_URL = os.getenv("VOICE_APP_URL", "http://voice-app:5000")

# In-memory notification queue (last 20 notifications)
notification_queue = deque(maxlen=20)
queue_lock = threading.Lock()

# Track processed emails to avoid duplicates
processed_emails = set()

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify({"status": "ok", "service": "email-monitor"}), 200


@app.route("/notifications", methods=["GET"])
def get_notifications():
    """Get all notifications in the queue."""
    with queue_lock:
        notifications = list(notification_queue)
    return jsonify({"notifications": notifications}), 200


@app.route("/notifications/clear", methods=["POST"])
def clear_notifications():
    """Clear all notifications."""
    with queue_lock:
        notification_queue.clear()
    return jsonify({"status": "cleared"}), 200


# ---------------------------------------------------------------------------
# Email Processing
# ---------------------------------------------------------------------------


def fetch_emails_from_gmail() -> list:
    """Fetch recent emails from Gmail via IMAP."""
    import imaplib
    import email as email_lib
    from datetime import datetime, timedelta

    try:
        # Gmail IMAP server
        imap = imaplib.IMAP4_SSL("imap.gmail.com", 993)

        # Login using Gmail address + App Password
        imap.login(GMAIL_ADDRESS, GMAIL_PASSWORD)

        imap.select("INBOX")

        # Search recent unseen emails
        since_date = datetime.utcnow() - timedelta(hours=2)
        since_str = since_date.strftime("%d-%b-%Y")

        status, messages = imap.search(None, f'(UNSEEN SINCE "{since_str}")')

        if status != "OK":
            logger.info("No new emails")
            return []

        email_ids = messages[0].split()
        logger.info(f"Found {len(email_ids)} new emails")

        emails = []

        for email_id in email_ids[-10:]:
            try:
                status, msg_data = imap.fetch(email_id, "(RFC822)")

                if status != "OK":
                    continue

                msg = email_lib.message_from_bytes(msg_data[0][1])

                sender = msg.get("From", "Unknown")
                subject = decode_header_str(msg.get("Subject", "(no subject)"))
                body = extract_body(msg)
                received_at = msg.get("Date", datetime.utcnow().isoformat())

                email_key = f"{sender}:{subject}:{received_at}"

                if email_key not in processed_emails:
                    emails.append({
                        "sender": sender,
                        "subject": subject,
                        "body": body,
                        "received_at": received_at,
                        "key": email_key,
                    })

                    processed_emails.add(email_key)

            except Exception as e:
                logger.error(f"Failed to parse email: {e}")
                continue

        imap.close()
        imap.logout()

        return emails

    except Exception as e:
        logger.error(f"Failed to fetch emails from Gmail: {e}", exc_info=True)
        return []


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


def classify_email(subject: str, body: str) -> dict:
    """Classify email as service-related using Ollama."""
    try:
        prompt = f"""Determine if this email is about a SERVICE CALL (machine problems, equipment issues, maintenance, technical support).

Subject: {subject}
Body: {body[:1000]}

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
            timeout=30,
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
    """Sync and classify emails, add notifications."""
    logger.info("Starting email sync...")
    try:
        emails = fetch_emails_from_gmail()
        logger.info(f"Processing {len(emails)} emails")

        for email_data in emails:
            # Classify
            classification = classify_email(email_data["subject"], email_data["body"])

            # Create notification
            notification = {
                "type": "service" if classification["is_service_related"] else "non_service",
                "sender": email_data["sender"],
                "subject": email_data["subject"],
                "body_preview": email_data["body"][:200],
                "reason": classification["reason"],
            }

            add_notification(notification)

            # Log
            if classification["is_service_related"]:
                logger.warning(f"SERVICE EMAIL: {email_data['subject']}")
            else:
                logger.info(f"Non-service email: {email_data['subject']}")

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


# Initialize on app startup
try:
    init_background_sync()
except Exception as e:
    logger.error(f"Failed to initialize background sync: {e}")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5003, debug=False, threaded=True)
