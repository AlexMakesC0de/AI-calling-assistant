"""Email text helpers for voice-app ingest."""

import re

_HTML_TAG_RE = re.compile(r"<[^>]+>")


def strip_html(text: str) -> str:
    if not text:
        return ""
    cleaned = _HTML_TAG_RE.sub("", text)
    cleaned = re.sub(r"\s+\n", "\n", cleaned)
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()


def build_email_transcript(subject: str, sender: str, body: str) -> str:
    """Format email fields into a transcript-shaped string for the formatter."""
    parts = []
    if subject:
        parts.append(f"Subject: {subject.strip()}")
    if sender:
        parts.append(f"From: {sender.strip()}")
    if body:
        parts.append(body.strip())
    return "\n\n".join(parts)
