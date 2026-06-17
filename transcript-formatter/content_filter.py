"""
Content filtering and text sanitization for the Transcript Formatter service.
"""

import json
import re
from config import (
    BASIC_FILTER_TERMS,
    TERM_FILTER_MODE,
    TERM_FILTER_CUSTOM_WORDS,
    TERM_FILTER_REPLACEMENT,
)


def _parse_custom_terms(raw: str) -> set[str]:
    stripped = raw.strip()
    if stripped.startswith("["):
        try:
            items = json.loads(stripped)
            return {str(t).strip().lower() for t in items if str(t).strip()}
        except json.JSONDecodeError:
            stripped = stripped.lstrip("[").rstrip("]")
    terms = set()
    for part in stripped.split(","):
        term = part.strip().lower()
        if term:
            terms.add(term)
    return terms


def _compile_pattern(terms: set[str]) -> re.Pattern | None:
    if not terms:
        return None
    alternation = "|".join(re.escape(t) for t in sorted(terms, key=len, reverse=True))
    return re.compile(rf"\b(?:{alternation})\b", re.IGNORECASE)


def _effective_filter_mode(metadata: dict) -> str:
    value = str(metadata.get("term_filter_mode") or TERM_FILTER_MODE or "basic").strip().lower()
    if value in ("none", "off", "disabled"):
        return "off"
    if value == "custom":
        return "custom"
    return "basic"


def _effective_filter_terms(mode: str, metadata: dict) -> set[str]:
    if mode == "off":
        return set()
    if mode == "basic":
        return set(BASIC_FILTER_TERMS)

    # custom mode
    custom_from_metadata = str(metadata.get("term_filter_custom_words") or "")
    source = custom_from_metadata if custom_from_metadata.strip() else TERM_FILTER_CUSTOM_WORDS
    return _parse_custom_terms(source)


def _sanitize_text_value(value: str, pattern: re.Pattern, replacement: str) -> tuple[str, bool]:
    if not isinstance(value, str) or pattern is None:
        return value, False

    if len(replacement) == 1:
        sub_fn = lambda m, r=replacement: r * len(m.group(0))
    else:
        sub_fn = replacement

    result = pattern.sub(sub_fn, value)
    return result, result != value


def filter_text(text: str, metadata: dict) -> str:
    """Apply the profanity filter to a plain string (e.g. raw transcript text)."""
    mode = _effective_filter_mode(metadata)
    blocked_terms = _effective_filter_terms(mode, metadata)
    if mode == "off" or not blocked_terms:
        return text
    pattern = _compile_pattern(blocked_terms)
    replacement = str(metadata.get("term_filter_replacement") or TERM_FILTER_REPLACEMENT)
    sanitized, _ = _sanitize_text_value(text, pattern, replacement)
    return sanitized


def _apply_content_filter(ai_fields: dict, metadata: dict) -> dict:
    mode = _effective_filter_mode(metadata)
    blocked_terms = _effective_filter_terms(mode, metadata)
    replacement = str(metadata.get("term_filter_replacement") or TERM_FILTER_REPLACEMENT)

    if mode == "off" or not blocked_terms:
        return ai_fields

    pattern = _compile_pattern(blocked_terms)

    filtered = dict(ai_fields)
    for key in ["caller_name", "agent_name", "issue_description", "call_summary", "error_messages"]:
        value = str(filtered.get(key, ""))
        sanitized, changed = _sanitize_text_value(value, pattern, replacement)
        if changed:
            filtered[key] = sanitized
            confidence_key = f"{key}_confidence"
            if confidence_key in filtered:
                filtered[confidence_key] = "low"

    return filtered
