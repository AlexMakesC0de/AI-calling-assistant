"""Email body and recipient helpers."""

import os
import re


_HTML_TAG_RE = re.compile(r"<[^>]+>")


def strip_html(text: str) -> str:
    """Convert HTML-ish content to plain text."""
    if not text:
        return ""
    cleaned = _HTML_TAG_RE.sub("", text)
    cleaned = re.sub(r"\s+\n", "\n", cleaned)
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()


def support_inbox_addresses() -> set[str]:
    """Configured support mailbox addresses (lowercase)."""
    raw = os.getenv("SUPPORT_INBOX_ADDRESSES") or os.getenv("GRAPH_MAILBOX") or ""
    if not raw.strip():
        return set()
    return {addr.strip().lower() for addr in raw.split(",") if addr.strip()}


def is_support_recipient(to_addresses: list[str], cc_addresses: list[str] | None = None) -> bool:
    """
    Return True when the message is addressed to a configured support inbox.
    When no filter is configured, all inbox messages pass (mailbox is already scoped).
    """
    allowed = support_inbox_addresses()
    if not allowed:
        return True
    recipients = {addr.lower() for addr in (to_addresses or []) if addr}
    recipients.update(addr.lower() for addr in (cc_addresses or []) if addr)
    return bool(recipients & allowed)
