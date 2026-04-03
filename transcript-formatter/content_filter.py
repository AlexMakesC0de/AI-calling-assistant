"""
Content filtering and text sanitization for the Transcript Formatter service.
"""

import re
from config import (
    BASIC_FILTER_TERMS,
    TERM_FILTER_MODE,
    TERM_FILTER_CUSTOM_WORDS,
    TERM_FILTER_REPLACEMENT,
)


def _parse_custom_terms(raw: str) -> set[str]:
    """Parse comma-separated custom filter terms."""
    terms = set()
    for part in raw.split(","):
        term = part.strip().lower()
        if term:
            terms.add(term)
    return terms


def _effective_filter_mode(metadata: dict) -> str:
    """Determine the effective filter mode from metadata or defaults."""
    value = str(metadata.get("term_filter_mode") or TERM_FILTER_MODE or "basic").strip().lower()
    if value in ("none", "off", "disabled"):
        return "off"
    if value == "custom":
        return "custom"
    return "basic"


def _effective_filter_terms(mode: str, metadata: dict) -> set[str]:
    """Get the effective set of filter terms based on mode."""
    if mode == "off":
        return set()
    if mode == "basic":
        return set(BASIC_FILTER_TERMS)

    # custom mode
    custom_from_metadata = str(metadata.get("term_filter_custom_words") or "")
    source = custom_from_metadata if custom_from_metadata.strip() else TERM_FILTER_CUSTOM_WORDS
    return _parse_custom_terms(source)


def _sanitize_text_value(value: str, blocked_terms: set[str], replacement: str) -> tuple[str, bool]:
    """
    Sanitize a text value by replacing blocked terms.
    
    Returns:
        Tuple of (sanitized_text, was_changed)
    """
    if not isinstance(value, str) or not blocked_terms:
        return value, False

    changed = False
    sanitized = value
    for term in blocked_terms:
        pattern = re.compile(rf"\\b{re.escape(term)}\\b", flags=re.IGNORECASE)
        updated = pattern.sub(replacement, sanitized)
        if updated != sanitized:
            changed = True
            sanitized = updated
    return sanitized, changed


def _apply_content_filter(ai_fields: dict, metadata: dict) -> dict:
    """
    Apply content filtering to AI-generated fields.
    
    Redacts sensitive terms and adjusts confidence scores for filtered fields.
    """
    mode = _effective_filter_mode(metadata)
    blocked_terms = _effective_filter_terms(mode, metadata)
    replacement = str(metadata.get("term_filter_replacement") or TERM_FILTER_REPLACEMENT)

    if mode == "off" or not blocked_terms:
        return ai_fields

    filtered = dict(ai_fields)
    for key in ["caller_name", "agent_name", "issue_description", "call_summary", "error_messages"]:
        value = str(filtered.get(key, ""))
        sanitized, changed = _sanitize_text_value(value, blocked_terms, replacement)
        if changed:
            filtered[key] = sanitized
            confidence_key = f"{key}_confidence"
            if confidence_key in filtered:
                filtered[confidence_key] = "low"

    return filtered
