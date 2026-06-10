"""
Robust extraction of a text body from inbound emails (ISR-349).

Support emails arrive in several shapes: plain text, multipart MIME with both
text/plain and text/html alternatives, and HTML-only. This module turns any of
them into the plain text the formatter should analyse, and degrades gracefully
on malformed input instead of failing the request.

Pairs with ``email_cleaning.clean_email_body`` — extract the body here first,
then strip signatures / quoted replies.
"""

from __future__ import annotations

import html as _html
import re
from email import message_from_bytes, message_from_string, policy
from email.message import EmailMessage

# Block-level tags whose close (or self-close) should become a line break so
# HTML structure isn't collapsed into one run-on line.
_BLOCK_BREAK_RE = re.compile(
    r"(?i)<\s*(br|/p|/div|/h[1-6]|/li|/tr|/blockquote)\s*/?\s*>"
)
_SCRIPT_STYLE_RE = re.compile(r"(?is)<\s*(script|style)[^>]*>.*?<\s*/\s*\1\s*>")
_TAG_RE = re.compile(r"(?s)<[^>]+>")
_HTML_HINT_RE = re.compile(r"(?i)<(html|body|div|p|br|table|span|a|img)\b")


def html_to_text(html: str) -> str:
    """Strip HTML to readable text without losing content.

    Removes script/style blocks, turns block-level tags into line breaks,
    drops remaining tags, and decodes HTML entities. Whitespace is collapsed
    but paragraph breaks are preserved.
    """
    if not html:
        return ""
    text = _SCRIPT_STYLE_RE.sub(" ", html)
    text = _BLOCK_BREAK_RE.sub("\n", text)
    text = _TAG_RE.sub("", text)
    text = _html.unescape(text)
    # Tidy whitespace: collapse runs of spaces/tabs, cap blank lines.
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _looks_like_html(text: str) -> bool:
    return bool(_HTML_HINT_RE.search(text or ""))


def _fallback_body(raw: str | bytes) -> str:
    """Last resort when MIME parsing fails: return text, stripping HTML if any."""
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", errors="replace")
    return html_to_text(raw) if _looks_like_html(raw) else raw.strip()


def extract_text_body(raw: str | bytes) -> str:
    """Extract the best plain-text body from a raw email message.

    Preference order: text/plain, then text/html (converted to text). Handles
    plain-text messages (no HTML stripping applied), multipart/alternative
    (prefers the text/plain part), and HTML-only messages. Malformed MIME falls
    back to the raw body.
    """
    if raw is None:
        return ""
    if (isinstance(raw, (str, bytes)) and not str(raw).strip()):
        return ""

    try:
        if isinstance(raw, bytes):
            msg: EmailMessage = message_from_bytes(raw, policy=policy.default)
        else:
            msg = message_from_string(raw, policy=policy.default)
    except Exception:
        return _fallback_body(raw)

    try:
        body_part = msg.get_body(preferencelist=("plain", "html"))
    except Exception:
        body_part = None

    if body_part is None:
        # Not a structured MIME body (e.g. a bare string) — use the payload.
        try:
            content = msg.get_content()
        except Exception:
            return _fallback_body(raw)
        if isinstance(content, bytes):
            content = content.decode("utf-8", errors="replace")
        content = str(content)
        return html_to_text(content) if _looks_like_html(content) else content.strip()

    try:
        content = body_part.get_content()
    except Exception:
        return _fallback_body(raw)
    if isinstance(content, bytes):
        content = content.decode("utf-8", errors="replace")
    content = str(content)

    if body_part.get_content_type() == "text/html":
        return html_to_text(content)
    # text/plain — route as-is, unless HTML slipped in untyped (e.g. a body
    # with no Content-Type header), in which case strip it safely.
    return html_to_text(content) if _looks_like_html(content) else content.strip()
