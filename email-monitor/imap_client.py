"""
Read mail via IMAP (Outlook.com, Gmail, etc.) without Microsoft Graph.

Outlook: app password — https://account.live.com/proofs/AppPassword
Gmail: enable IMAP + app password — https://myaccount.google.com/apppasswords
Set OUTLOOK_IMAP_HOST=imap.gmail.com for Gmail (default: outlook.office365.com).
"""

from __future__ import annotations

import email
import imaplib
import logging
import os
from email.header import decode_header
from typing import Any

logger = logging.getLogger(__name__)

IMAP_HOST = os.getenv("OUTLOOK_IMAP_HOST", "outlook.office365.com")
IMAP_PORT = int(os.getenv("OUTLOOK_IMAP_PORT", "993"))


class ImapConfigError(Exception):
    """Missing or invalid IMAP settings."""


def imap_user() -> str:
    value = (
        os.getenv("OUTLOOK_IMAP_USER")
        or os.getenv("OUTLOOK_EMAIL")
        or os.getenv("GRAPH_MAILBOX")
        or ""
    ).strip()
    if not value:
        raise ImapConfigError(
            "OUTLOOK_IMAP_USER is required (your @outlook.com support test address)."
        )
    return value


def imap_password() -> str:
    value = (os.getenv("OUTLOOK_IMAP_PASSWORD") or os.getenv("OUTLOOK_APP_PASSWORD") or "").strip()
    if not value:
        raise ImapConfigError(
            "OUTLOOK_IMAP_PASSWORD is required (Outlook app password, not your login password)."
        )
    return value


def is_configured() -> bool:
    try:
        imap_user()
        imap_password()
        return True
    except ImapConfigError:
        return False


def _decode_header_value(value: str | None) -> str:
    if not value:
        return ""
    parts: list[str] = []
    for fragment, encoding in decode_header(value):
        if isinstance(fragment, bytes):
            parts.append(fragment.decode(encoding or "utf-8", errors="replace"))
        else:
            parts.append(str(fragment))
    return "".join(parts)


def _extract_plain_body(msg: email.message.Message) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain" and part.get_content_disposition() != "attachment":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    return payload.decode(charset, errors="replace")
        for part in msg.walk():
            if part.get_content_type() == "text/html" and part.get_content_disposition() != "attachment":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    return payload.decode(charset, errors="replace")
        return ""
    payload = msg.get_payload(decode=True)
    if not payload:
        return ""
    charset = msg.get_content_charset() or "utf-8"
    return payload.decode(charset, errors="replace")


def connect() -> imaplib.IMAP4_SSL:
    mail = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
    mail.login(imap_user(), imap_password())
    return mail


def verify_access() -> dict[str, Any]:
    mail = connect()
    try:
        status, data = mail.select("INBOX", readonly=True)
        ok = status == "OK"
        message_count = int(data[0]) if ok and data and data[0] else 0
        return {
            "auth_mode": "imap",
            "mailbox": imap_user(),
            "imap_host": IMAP_HOST,
            "ok": ok,
            "inbox_messages": message_count,
        }
    finally:
        try:
            mail.logout()
        except Exception:
            pass


def fetch_unseen_emails(*, limit: int = 10) -> list[dict[str, Any]]:
    """Return unseen inbox messages in the same shape as Graph fetch."""
    mail = connect()
    emails: list[dict[str, Any]] = []

    try:
        mail.select("INBOX", readonly=True)
        status, data = mail.search(None, "UNSEEN")
        if status != "OK" or not data or not data[0]:
            return []

        ids = data[0].split()
        for msg_id in ids[-limit:]:
            status, fetched = mail.fetch(msg_id, "(RFC822)")
            if status != "OK" or not fetched:
                continue

            raw = fetched[0][1]
            msg = email.message_from_bytes(raw)
            subject = _decode_header_value(msg.get("Subject"))
            sender = _decode_header_value(msg.get("From"))
            received_at = _decode_header_value(msg.get("Date"))
            body = _extract_plain_body(msg)[:2000]
            message_id = _decode_header_value(msg.get("Message-ID")) or msg_id.decode()

            email_key = f"{sender}:{subject}:{received_at}"
            emails.append(
                {
                    "sender": sender,
                    "subject": subject,
                    "body": body,
                    "received_at": received_at,
                    "key": email_key,
                    "message_id": message_id,
                    "attachments": [],
                    "source": "imap",
                }
            )
    finally:
        try:
            mail.logout()
        except Exception:
            pass

    return emails
