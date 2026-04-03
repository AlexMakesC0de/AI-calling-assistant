"""
Transcript analysis and processing for the Transcript Formatter service.
"""

import re
from config import NON_ACTION_STEP_PATTERNS, ACTION_HINT_PATTERNS


def _extract_caller_name_from_transcript(transcript: str) -> str | None:
    """Extract caller name from common self-introduction phrases."""
    patterns = [
        r"\bmy name is\s+([a-z][a-z\-']+(?:\s+[a-z][a-z\-']+)?)",
        r"\bthis is\s+([a-z][a-z\-']+(?:\s+[a-z][a-z\-']+)?)",
        r"\bi am\s+([a-z][a-z\-']+(?:\s+[a-z][a-z\-']+)?)",
        r"\bi'm\s+([a-z][a-z\-']+(?:\s+[a-z][a-z\-']+)?)",
    ]
    for pattern in patterns:
        match = re.search(pattern, transcript, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip().title()
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


def _apply_transcript_heuristics(ai_fields: dict, transcript: str) -> dict:
    """Backfill required fields from transcript when LLM output is weak."""
    merged = dict(ai_fields)

    caller_name = str(merged.get("caller_name", "")).strip()
    if not caller_name or caller_name.lower() == "not mentioned":
        extracted_name = _extract_caller_name_from_transcript(transcript)
        if extracted_name:
            merged["caller_name"] = extracted_name
            merged["caller_name_confidence"] = "high"

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
