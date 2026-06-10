"""
Transcript analysis and processing for the Transcript Formatter service.
"""

import re
from config import NON_ACTION_STEP_PATTERNS, ACTION_HINT_PATTERNS
from word_lists import normalize_name, name_in_db, TUSSENVOEGELS

# The LLM occasionally writes the company name "Repak" as "Repack" etc. Match
# whole words only so unrelated words like "repacking" are left alone.
_REPAK_RE = re.compile(r"\b(?:rapack|repack|re-pak)\b", re.IGNORECASE)


def _normalize_proper_nouns(ai_fields: dict) -> dict:
    """Correct misspelled proper nouns (e.g. "Repack" -> "Repak") in place.

    Walks every string value and every string inside list values, leaving
    non-string values untouched.
    """
    def fix(value):
        if isinstance(value, str):
            return _REPAK_RE.sub("Repak", value)
        if isinstance(value, list):
            return [fix(item) for item in value]
        return value

    for key, value in ai_fields.items():
        ai_fields[key] = fix(value)
    return ai_fields

# Capture up to 4 words to accommodate "first [tussenvoegel...] last"
_NAME_CAPTURE = r"([a-z][a-z\-']+(?:\s+[a-z][a-z\-']+){0,3})"

_INTRO_PATTERNS = [
    rf"\bmy name is\s+{_NAME_CAPTURE}",
    rf"\bthis is\s+{_NAME_CAPTURE}",
    rf"\bi am\s+{_NAME_CAPTURE}",
    rf"\bi'm\s+{_NAME_CAPTURE}",
    # Dutch introductions
    rf"\bmijn naam is\s+{_NAME_CAPTURE}",
    rf"\bu spreekt met\s+{_NAME_CAPTURE}",
    rf"\bmet\s+{_NAME_CAPTURE}",
    rf"\bhier is\s+{_NAME_CAPTURE}",
    rf"\bhier spreekt\s+{_NAME_CAPTURE}",
    rf"\byou(?:'re| are) speaking with\s+{_NAME_CAPTURE}",
    rf"\bspeaking with\s+{_NAME_CAPTURE}",
]


def _extract_caller_name_from_transcript(transcript: str) -> str | None:
    """Extract caller name from common self-introduction phrases (EN + NL)."""
    for pattern in _INTRO_PATTERNS:
        match = re.search(pattern, transcript, flags=re.IGNORECASE)
        if match:
            return normalize_name(match.group(1).strip())
    return None


def _build_summary_from_transcript(transcript: str) -> str:
    """Build a short fallback summary from transcript sentences."""
    clean = transcript.strip()
    if not clean:
        return "No summary available."
    sentences = re.split(r"(?<=[.!?])\s+", clean)
    sentences = [s.strip() for s in sentences if s.strip()]
    if not sentences:
        return clean[:320]
    return " ".join(sentences[:3])[:480]


def _validate_and_normalize_name(name: str) -> tuple[str, str | None]:
    """Return (normalized_name, confidence_override_or_None).

    - Normalizes casing (tussenvoegels stay lowercase mid-name).
    - If the name is in the DB, upgrades confidence to "high".
    - If the name looks like a non-name (single uppercase word not in DB,
      or contains digits), returns the name unchanged with confidence "low".
    """
    words = name.strip().split()
    if not words or not 1 <= len(words) <= 5:
        return name, "low"

    normalized = normalize_name(name)

    # Reject obvious non-names: single word that is all-uppercase or contains digits
    if len(words) == 1:
        if re.search(r"\d", words[0]):
            return normalized, "low"

    # Boost confidence when first name is in the DB
    if name_in_db(name):
        return normalized, "high"

    return normalized, None


def _apply_transcript_heuristics(ai_fields: dict, transcript: str) -> dict:
    """Backfill required fields from transcript when LLM output is weak."""
    merged = dict(ai_fields)

    caller_name = str(merged.get("caller_name", "")).strip()
    if not caller_name or caller_name.lower() == "not mentioned":
        extracted_name = _extract_caller_name_from_transcript(transcript)
        if extracted_name:
            merged["caller_name"] = extracted_name
            merged["caller_name_confidence"] = "high"
    elif caller_name.lower() not in ("not mentioned",):
        # LLM gave us a name — normalize casing and optionally adjust confidence
        normalized, conf_override = _validate_and_normalize_name(caller_name)
        merged["caller_name"] = normalized
        if conf_override:
            merged["caller_name_confidence"] = conf_override

    agent_name = str(merged.get("agent_name", "")).strip()
    if agent_name and agent_name.lower() not in ("not mentioned",):
        normalized, conf_override = _validate_and_normalize_name(agent_name)
        merged["agent_name"] = normalized
        if conf_override:
            merged["agent_name_confidence"] = conf_override

    call_summary = str(merged.get("call_summary", "")).strip()
    if not call_summary or call_summary.lower() == "not mentioned":
        merged["call_summary"] = _build_summary_from_transcript(transcript)
        merged["call_summary_confidence"] = "medium"

    issue_description = str(merged.get("issue_description", "")).strip()
    if not issue_description or issue_description.lower() == "not mentioned":
        merged["issue_description"] = _build_summary_from_transcript(transcript)
        merged["issue_description_confidence"] = "medium"

    return merged


def _is_non_action_step(step: str) -> bool:
    """Return True when a step is clearly not an agent troubleshooting action."""
    text = step.strip().lower()
    if not text:
        return True
    if len(text.split()) <= 3:
        return True
    if text.endswith("?"):
        return True
    for pattern in NON_ACTION_STEP_PATTERNS:
        if re.search(pattern, text, flags=re.IGNORECASE):
            return True
    return False


def _looks_actionable_step(step: str) -> bool:
    """Return True when text looks like an agent action."""
    text = step.strip()
    if not text or _is_non_action_step(text):
        return False
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in ACTION_HINT_PATTERNS)


def _extract_agent_actions_from_transcript(transcript: str) -> list[str]:
    """Extract likely agent actions from diarized transcript lines."""
    lines = [line.strip() for line in transcript.splitlines() if line.strip()]
    speaker_lines = [line for line in lines if re.match(r"^speaker\s*\d+\s*:", line, flags=re.IGNORECASE)]
    if not speaker_lines:
        return []

    first_match = re.match(r"^(speaker\s*\d+)\s*:", speaker_lines[0], flags=re.IGNORECASE)
    if not first_match:
        return []
    likely_agent = first_match.group(1).lower().replace(" ", "")

    actions: list[str] = []
    seen = set()
    for line in speaker_lines:
        match = re.match(r"^(speaker\s*\d+)\s*:\s*(.*)$", line, flags=re.IGNORECASE)
        if not match:
            continue
        speaker = match.group(1).lower().replace(" ", "")
        text = match.group(2).strip()
        if speaker != likely_agent:
            continue
        if not _looks_actionable_step(text):
            continue
        normalized = text.rstrip(". ")
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        actions.append(normalized)
        if len(actions) >= 4:
            break
    return actions


def _sanitize_steps_taken(transcript: str, steps_taken) -> list[str]:
    """Keep only concrete, relevant agent actions for the steps_taken field."""
    if isinstance(steps_taken, str):
        candidate_steps = [steps_taken]
    elif isinstance(steps_taken, list):
        candidate_steps = [str(s).strip() for s in steps_taken if str(s).strip()]
    else:
        candidate_steps = []

    cleaned: list[str] = []
    seen = set()
    for step in candidate_steps:
        if not _looks_actionable_step(step):
            continue
        normalized = step.rstrip(". ")
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(normalized)

    if cleaned:
        return cleaned[:4]

    return _extract_agent_actions_from_transcript(transcript)
