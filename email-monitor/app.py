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
import jwt

from msal import PublicClientApplication
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
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
OLLAMA_CONNECT_TIMEOUT = int(os.getenv("OLLAMA_CONNECT_TIMEOUT", "3"))
OLLAMA_READ_TIMEOUT = int(os.getenv("OLLAMA_READ_TIMEOUT", "120"))
VOICE_APP_URL = os.getenv("VOICE_APP_URL", "http://voice-app:5000")
CLIENT_ID = os.getenv("CLIENT_ID", "cec316e6-66fe-4e58-9bc0-c4f5a32d43a1")
TENANT_ID = os.getenv("TENANT_ID", "eefd9f50-7c95-4873-ad2e-3f436680b76c")

# In-memory notification queue (last 20 notifications)
notification_queue = deque(maxlen=20)
queue_lock = threading.Lock()

GRAPH_TOKEN = None

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

def get_graph_token():

    app = PublicClientApplication(
        CLIENT_ID,
        authority=f"https://login.microsoftonline.com/{TENANT_ID}"
    )

    flow = app.initiate_device_flow(scopes=["Mail.Read", "User.Read"])

    logger.warning(flow["message"])  # login instruction

    import time

    while True:
        result = app.acquire_token_by_device_flow(flow)

        if "access_token" in result:
            return result["access_token"]

        if result.get("error") == "authorization_pending":
            time.sleep(flow["interval"])
            continue

        raise Exception(result)

    return result["access_token"]

def fetch_emails_from_graph(token: str) -> list:
    """Fetch recent emails using Microsoft Graph API."""

    headers = {
        "Authorization": f"Bearer {token}"
    }

    url = "https://graph.microsoft.com/v1.0/me/mailFolders/inbox/messages?$top=10"

    response = requests.get(url, headers=headers, timeout=30)

    print(requests.get(
        "https://graph.microsoft.com/v1.0/me",
        headers={"Authorization": f"Bearer {token}"}
    ).json())

    print(requests.get(
        "https://graph.microsoft.com/v1.0/me/mailboxSettings",
        headers={"Authorization": f"Bearer {token}"}
    ).status_code)

    logger.error(f"GRAPH STATUS: {response.status_code}")
    logger.error(f"GRAPH RESPONSE: {response.text}")

    response.raise_for_status()

    data = response.json()
    messages = data.get("value", [])

    emails = []

    for msg in messages:
        subject = msg.get("subject", "")
        sender = (msg.get("from", {}) or {}).get("emailAddress", {}).get("address", "")
        body = (msg.get("bodyPreview", "") or "")
        received_at = msg.get("receivedDateTime", "")

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

    return emails


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

        emails = fetch_emails_from_graph(GRAPH_TOKEN)

        logger.info(f"Processing {len(emails)} emails")

        for email_data in emails:
            classification = classify_email(email_data["subject"], email_data["body"])

            notification = {
                "type": "service" if classification["is_service_related"] else "non_service",
                "sender": email_data["sender"],
                "subject": email_data["subject"],
                "body_preview": email_data["body"][:200],
                "reason": classification["reason"],
            }

            add_notification(notification)

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
    GRAPH_TOKEN = get_graph_token()
    print(jwt.decode(GRAPH_TOKEN, options={"verify_signature": False}))
    init_background_sync()
except Exception as e:
    logger.error(f"Failed to initialize background sync: {e}")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5003, debug=False, threaded=True)
