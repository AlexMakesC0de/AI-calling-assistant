"""
Output filters for the Transcript Formatter service (ISR-355).

Three independently-configurable filters run on the LLM-extracted form before
it is persisted by downstream consumers:

  apply_pii_redaction         - scrubs caller names and phone / email PII from
                                the structured form fields and free-text body
                                before persistence
  evaluate_confidence_review  - flags the form for engineer review when the
                                LLM's confidence is too low to trust
  detect_off_topic            - reports when the LLM's output does not appear
                                to relate to the input transcript, so the
                                caller can trigger a clarifying retry

Each filter is wired in independently and respects both environment-variable
defaults (see ``config.py``) and per-request overrides on the request
``metadata`` block.
"""

from __future__ import annotations

import logging
import re

from config import (
    OUTPUT_FILTER_REDACT_PII,
    OUTPUT_FILTER_PII_FIELDS,
    OUTPUT_FILTER_PII_REPLACEMENT,
    OUTPUT_FILTER_LOW_CONF_REVIEW,
    OUTPUT_FILTER_LOW_CONF_OVERALL,
    OUTPUT_FILTER_LOW_CONF_MIN_FIELDS,
    OUTPUT_FILTER_OFFTOPIC_DETECT,
    OUTPUT_FILTER_OFFTOPIC_THRESHOLD,
    OUTPUT_FILTER_OFFTOPIC_MIN_TOKENS,
)

logger = logging.getLogger(__name__)

_TRUTHY = {"1", "true", "yes", "on"}
_FALSY = {"0", "false", "no", "off"}
_NEUTRAL_VALUES = {"", "not mentioned", "none", "n/a", "na", "unknown"}


def _as_bool(value, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in _TRUTHY:
        return True
    if text in _FALSY:
        return False
    return default


def _is_neutral(value) -> bool:
    return str(value or "").strip().lower() in _NEUTRAL_VALUES


# ---------------------------------------------------------------------------
# PII redaction
# ---------------------------------------------------------------------------

# Phone numbers: tolerant of spaces, dots, hyphens, parentheses, and a +country
# code. The negative lookarounds + 8-digit floor stop short numeric tails like
# the "5012" in "ERR-5012" from being eaten.
_PHONE_RE = re.compile(
    r"(?<!\w)(?:\+?\d[\d\s().\-]{6,}\d)(?!\w)"
)
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")

_PII_FREE_TEXT_FIELDS = (
    "issue_description", "resolution_outcome", "call_summary", "error_messages",
)
# call_summary is excluded here: operators need the caller name in the summary
# for context. Phone/email are still redacted via _PII_FREE_TEXT_FIELDS above.
_PII_NAME_REDACT_TEXT_FIELDS = (
    "issue_description", "resolution_outcome", "error_messages",
)
_PII_FREE_LIST_FIELDS = ("steps_taken", "follow_up_actions")


def _pii_settings(metadata: dict | None) -> dict:
    md = metadata or {}
    enabled = _as_bool(md.get("redact_pii"), OUTPUT_FILTER_REDACT_PII)

    raw_fields = md.get("redact_pii_fields")
    if isinstance(raw_fields, list):
        fields = [str(f).strip() for f in raw_fields if str(f).strip()]
    elif isinstance(raw_fields, str) and raw_fields.strip():
        fields = [f.strip() for f in raw_fields.split(",") if f.strip()]
    else:
        fields = list(OUTPUT_FILTER_PII_FIELDS)

    replacement = str(md.get("redact_pii_replacement")
                      or OUTPUT_FILTER_PII_REPLACEMENT)
    return {"enabled": enabled, "fields": fields, "replacement": replacement}


def _redact_phones_and_emails(text: str, replacement: str) -> str:
    if not text:
        return text
    text = _EMAIL_RE.sub(replacement, text)
    text = _PHONE_RE.sub(replacement, text)
    return text


# Dutch / German / Spanish name particles that should not themselves be
# redacted ("Hannah de Jong" → redact Hannah and Jong, but not "de").
_NAME_PARTICLES = {"de", "der", "den", "van", "von", "del", "la", "le",
                   "di", "da", "el", "los", "las"}

_COMMON_WORDS = {
    # Dutch common words that should never be redacted as names
    "deze", "heeft", "voor", "meer", "zijn", "werd", "worden", "maar",
    "kunnen", "moeten", "willen", "zullen", "iemand", "niets", "alles",
    "echter", "omdat", "wanneer", "waardoor", "daarna", "hierbij",
    # English equivalents
    "this", "that", "from", "have", "been", "will", "were", "they",
    "some", "more", "when", "than", "then", "also",
}


def _redact_name_occurrences(text: str, name: str, replacement: str) -> str:
    """Redact any occurrence of a known caller name in free text.

    Redacts the full name AND each individual name token (e.g. "Maria
    Hendriks" → also redacts a standalone "Maria"). LLM summaries often
    drop the surname and refer to the customer by first name, so
    redacting the full string alone would leak the first name.
    """
    if not text or not name or _is_neutral(name):
        return text

    full = name.strip()
    candidates = [full]
    for token in re.split(r"\s+", full):
        token = token.strip("'-")
        if len(token) >= 4 and token.lower() not in _NAME_PARTICLES and token.lower() not in _COMMON_WORDS:
            candidates.append(token)

    # Apply longest first so the full phrase is replaced before its parts;
    # otherwise the first-name pass would split "Maria Hendriks" into
    # "[redacted] Hendriks" before the full-name pattern could match.
    seen: set[str] = set()
    ordered: list[str] = []
    for candidate in sorted(candidates, key=len, reverse=True):
        key = candidate.lower()
        if key and key not in seen:
            seen.add(key)
            ordered.append(candidate)

    result = text
    for candidate in ordered:
        pattern = re.compile(
            r"\b" + re.escape(candidate) + r"\b", re.IGNORECASE,
        )
        result = pattern.sub(replacement, result)
    return result


def apply_pii_redaction(ai_fields: dict,
                        metadata: dict | None = None) -> dict:
    """Redact PII from the LLM-extracted fields, returning a new dict.

    Two passes:
      - the structured identity fields named in ``OUTPUT_FILTER_PII_FIELDS``
        (default ``caller_name``, ``contact_info``) are replaced wholesale
      - the free-text body (issue description / outcome / summary / error
        messages / steps_taken / follow_up_actions) is scanned for phone
        numbers, email addresses, and explicit mentions of the caller name
    """
    settings = _pii_settings(metadata)
    if not settings["enabled"]:
        return ai_fields

    fields = settings["fields"]
    replacement = settings["replacement"]
    out = dict(ai_fields)

    # Capture the name BEFORE the identity fields are scrubbed; we still want
    # to redact mentions of it inside free-text fields.
    raw_caller_name = str(out.get("caller_name") or "").strip()

    for field in fields:
        if field in out and not _is_neutral(out.get(field, "")):
            out[field] = replacement

    for field in _PII_FREE_TEXT_FIELDS:
        value = out.get(field)
        if isinstance(value, str) and value:
            scrubbed = _redact_phones_and_emails(value, replacement)
            if field in _PII_NAME_REDACT_TEXT_FIELDS:
                scrubbed = _redact_name_occurrences(
                    scrubbed, raw_caller_name, replacement,
                )
            out[field] = scrubbed

    for field in _PII_FREE_LIST_FIELDS:
        value = out.get(field)
        if isinstance(value, list):
            cleaned: list = []
            for item in value:
                if isinstance(item, str):
                    item = _redact_phones_and_emails(item, replacement)
                    item = _redact_name_occurrences(
                        item, raw_caller_name, replacement,
                    )
                cleaned.append(item)
            out[field] = cleaned

    return out


# ---------------------------------------------------------------------------
# Low-confidence review flag
# ---------------------------------------------------------------------------

_CONFIDENCE_RANK = {"low": 1, "medium": 2, "high": 3}


def _review_settings(metadata: dict | None) -> dict:
    md = metadata or {}
    enabled = _as_bool(md.get("low_confidence_review"),
                       OUTPUT_FILTER_LOW_CONF_REVIEW)
    overall = str(md.get("low_confidence_overall")
                  or OUTPUT_FILTER_LOW_CONF_OVERALL).strip().lower()
    if overall not in _CONFIDENCE_RANK:
        overall = OUTPUT_FILTER_LOW_CONF_OVERALL
    try:
        min_fields = int(md.get("low_confidence_min_fields",
                                OUTPUT_FILTER_LOW_CONF_MIN_FIELDS))
    except (TypeError, ValueError):
        min_fields = OUTPUT_FILTER_LOW_CONF_MIN_FIELDS
    return {"enabled": enabled, "overall": overall, "min_fields": min_fields}


def evaluate_confidence_review(confidence: dict,
                               metadata: dict | None = None) -> dict:
    """Decide whether the form needs engineer review based on confidence.

    Reads the ``confidence`` dict produced by ``_extract_confidence``
    (``overall``, ``low_confidence_fields``). Returns
    ``{"required": bool, "reasons": [...]}`` with short reason codes that
    downstream consumers can switch on.
    """
    settings = _review_settings(metadata)
    if not settings["enabled"] or not isinstance(confidence, dict):
        return {"required": False, "reasons": []}

    overall_text = str(confidence.get("overall") or "").lower()
    low_fields = list(confidence.get("low_confidence_fields") or [])

    reasons: list[str] = []
    threshold_rank = _CONFIDENCE_RANK.get(settings["overall"], 1)
    overall_rank = _CONFIDENCE_RANK.get(overall_text, 3)
    if overall_rank <= threshold_rank:
        reasons.append("overall_confidence_below_threshold")
    if len(low_fields) >= settings["min_fields"]:
        reasons.append("many_low_confidence_fields")

    return {"required": bool(reasons), "reasons": reasons}


# ---------------------------------------------------------------------------
# Off-topic detection
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(r"[A-Za-zÀ-ÿ0-9'\-]{4,}")
# Filtered so common conversational filler does not inflate the overlap
# score. Mix of high-frequency English/Dutch terms plus diarization markers
# that appear in every transcript.
_STOP_TOKENS = {
    "this", "that", "with", "from", "have", "your", "their", "would", "could",
    "should", "about", "there", "which", "while", "been", "very", "really",
    "just", "into", "such", "what", "when", "where", "then", "than", "still",
    "going", "doing", "said", "today", "they", "them", "those", "also", "much",
    "more", "less", "even", "every", "thing", "things", "ever", "back", "yeah",
    "okay", "alright", "thank", "thanks", "hello", "hi",
    "speaker", "agent", "caller",
    "voor", "naar", "deze", "waar", "maar", "wij", "jij", "hij", "het", "een",
    "die", "dat", "ook", "kan", "wat", "wel", "niet", "mijn",
}


def _content_tokens(text: str) -> set[str]:
    if not text:
        return set()
    return {
        token.lower()
        for token in _TOKEN_RE.findall(text)
        if token.lower() not in _STOP_TOKENS
    }


def _output_text(ai_fields: dict) -> str:
    """Flatten the LLM's free-text fields into one body for overlap scoring."""
    parts: list[str] = []
    for field in ("issue_description", "resolution_outcome", "call_summary",
                  "error_messages"):
        value = ai_fields.get(field)
        if isinstance(value, str):
            parts.append(value)
    for field in ("steps_taken", "follow_up_actions"):
        value = ai_fields.get(field)
        if isinstance(value, list):
            parts.extend(str(item) for item in value if isinstance(item, str))
    return "\n".join(parts)


def _offtopic_settings(metadata: dict | None) -> dict:
    md = metadata or {}
    enabled = _as_bool(md.get("offtopic_detect"),
                       OUTPUT_FILTER_OFFTOPIC_DETECT)
    try:
        threshold = float(md.get("offtopic_threshold",
                                 OUTPUT_FILTER_OFFTOPIC_THRESHOLD))
    except (TypeError, ValueError):
        threshold = OUTPUT_FILTER_OFFTOPIC_THRESHOLD
    try:
        min_tokens = int(md.get("offtopic_min_tokens",
                                OUTPUT_FILTER_OFFTOPIC_MIN_TOKENS))
    except (TypeError, ValueError):
        min_tokens = OUTPUT_FILTER_OFFTOPIC_MIN_TOKENS
    return {"enabled": enabled, "threshold": threshold,
            "min_tokens": min_tokens}


def detect_off_topic(transcript: str, ai_fields: dict,
                     metadata: dict | None = None) -> dict:
    """Decide whether the LLM's output looks unrelated to the transcript.

    Compares lowercased content tokens (≥4 letters/digits, stop words and
    diarization markers removed) in the LLM's free-text fields against the
    transcript. Returns ``{"off_topic": bool, "overlap": float,
    "reason": str | None}``.

    Returns ``off_topic=False`` when the output is too short to judge — the
    prompt's "Not mentioned" boilerplate would otherwise produce false
    positives on short calls.
    """
    settings = _offtopic_settings(metadata)
    if not settings["enabled"]:
        return {"off_topic": False, "overlap": 1.0, "reason": None}

    output_tokens = _content_tokens(_output_text(ai_fields))
    if len(output_tokens) < settings["min_tokens"]:
        return {"off_topic": False, "overlap": 1.0,
                "reason": "output too short to judge"}

    transcript_tokens = _content_tokens(transcript)
    if not transcript_tokens:
        return {"off_topic": False, "overlap": 1.0,
                "reason": "transcript had no content tokens"}

    overlap = round(
        len(output_tokens & transcript_tokens) / len(output_tokens), 4,
    )
    if overlap < settings["threshold"]:
        return {
            "off_topic": True,
            "overlap": overlap,
            "reason": (
                f"output content overlap {overlap:.2f} below threshold "
                f"{settings['threshold']:.2f}"
            ),
        }
    return {"off_topic": False, "overlap": overlap, "reason": None}
