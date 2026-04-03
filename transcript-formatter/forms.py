"""
Form building and translation for the Transcript Formatter service.
"""

import logging
import re
import time
import uuid
from datetime import datetime, timezone

from config import (
    OLLAMA_URL,
    OLLAMA_CONNECT_TIMEOUT,
    OLLAMA_TRANSLATE_READ_TIMEOUT,
    TRANSLATION_TIME_BUDGET,
    TRANSLATION_CHUNK_MAX_CHARS,
    DEFAULT_INCLUDE_DUTCH_TRANSLATION,
)
from ollama_client import _ai_fill_form, _resolve_ollama_model, _strip_markdown_fences
from transcript_processor import (
    _apply_transcript_heuristics,
    _sanitize_steps_taken,
)
from content_filter import _apply_content_filter
from confidence_scoring import _extract_confidence
import requests

logger = logging.getLogger(__name__)
http_client = requests.Session()


def _looks_like_translation_refusal(text: str) -> bool:
    """Check if model response looks like a refusal to translate."""
    value = (text or "").strip().lower()
    if not value:
        return False
    refusal_markers = [
        "ik kan niet",
        "kan niet helpen",
        "i can't",
        "i cannot",
        "can't assist",
        "cannot assist",
        "niet meewerken",
        "sorry",
    ]
    return any(marker in value for marker in refusal_markers)


def _normalize_for_compare(text: str) -> str:
    """Normalize text for comparison (alphanumeric only, lowercase)."""
    return re.sub(r"[^a-z0-9]+", "", (text or "").strip().lower())


def _as_bool(value: object, default: bool = True) -> bool:
    """Convert value to boolean with fallback to default."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in ("1", "true", "yes", "on"):
        return True
    if text in ("0", "false", "no", "off"):
        return False
    return default


def _likely_untranslated_english(source: str, translated: str) -> bool:
    """Detect if translation output is just the original English text."""
    src = (source or "").strip()
    dst = (translated or "").strip()
    if not src or not dst:
        return False

    # If normalized texts are identical and source seems English, treat as untranslated.
    if _normalize_for_compare(src) != _normalize_for_compare(dst):
        return False

    english_markers = [
        " the ", " and ", " please ", " account ", " error ", "password", "cannot", "can't",
    ]
    src_l = f" {src.lower()} "
    return any(marker in src_l for marker in english_markers)


def _translate_text_to_dutch(text: str, deadline: float | None = None) -> str:
    """Translate text to Dutch and return source text on failure."""
    source = (text or "").strip()
    if not source:
        return text

    known_map = {
        "No summary available.": "Geen samenvatting beschikbaar.",
        "Not mentioned": "Niet vermeld",
        "Unable to determine — AI unavailable.": "Niet te bepalen — AI niet beschikbaar.",
    }
    if source in known_map:
        return known_map[source]

    # Chunk long transcripts to avoid single-call timeout failures.
    chunks: list[str] = []
    current = ""
    for sentence in [s.strip() for s in re.split(r"(?<=[.!?])\s+", source) if s.strip()]:
        if len(sentence) >= TRANSLATION_CHUNK_MAX_CHARS:
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(
                [
                    sentence[i : i + TRANSLATION_CHUNK_MAX_CHARS]
                    for i in range(0, len(sentence), TRANSLATION_CHUNK_MAX_CHARS)
                ]
            )
            continue

        candidate = f"{current} {sentence}".strip() if current else sentence
        if current and len(candidate) > TRANSLATION_CHUNK_MAX_CHARS:
            chunks.append(current)
            current = sentence
        else:
            current = candidate

    if current:
        chunks.append(current)
    if not chunks:
        chunks = [source]
    translated_parts: list[str] = []

    for idx, chunk in enumerate(chunks):
        if deadline and time.monotonic() > deadline:
            logger.warning(
                "Translation time budget exhausted at chunk %d/%d; keeping remaining text as-is.",
                idx + 1, len(chunks),
            )
            translated_parts.extend(chunks[idx:])
            break

        prompt = (
            "You are a professional English-to-Dutch translator. "
            "Translate the following text to Dutch (nl-NL). "
            "Output ONLY the Dutch translation. Keep names, IDs, and error codes unchanged. "
            "Do not add explanation, commentary, or markdown.\n\n"
            f"TEXT:\n{chunk}"
        )

        try:
            model_name = _resolve_ollama_model()
            resp = http_client.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": model_name,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.0, "num_predict": 400},
                },
                timeout=(OLLAMA_CONNECT_TIMEOUT, OLLAMA_TRANSLATE_READ_TIMEOUT),
            )
            resp.raise_for_status()
            translated = _strip_markdown_fences(resp.json().get("response", "")).strip()

            if _looks_like_translation_refusal(translated):
                retry_prompt = (
                    "Task: translation only. Translate to Dutch (nl-NL) literally. "
                    "Do not refuse, do not provide warnings, do not summarize. "
                    "Keep unknown tokens as-is. Return translated text only.\n\n"
                    f"TEXT:\n{chunk}"
                )
                retry_resp = http_client.post(
                    f"{OLLAMA_URL}/api/generate",
                    json={
                        "model": model_name,
                        "prompt": retry_prompt,
                        "stream": False,
                        "options": {"temperature": 0.0, "num_predict": 400},
                    },
                    timeout=(OLLAMA_CONNECT_TIMEOUT, OLLAMA_TRANSLATE_READ_TIMEOUT),
                )
                retry_resp.raise_for_status()
                retry_text = _strip_markdown_fences(
                    retry_resp.json().get("response", "")
                ).strip()
                if retry_text and not _looks_like_translation_refusal(retry_text):
                    translated = retry_text

            translated_parts.append(translated or chunk)
        except Exception as exc:
            logger.warning(
                "Dutch translation failed for chunk %s/%s, using original chunk: %s",
                idx + 1,
                len(chunks),
                exc,
            )
            translated_parts.append(chunk)

    return "\n".join(part for part in translated_parts if part).strip() or text


def _estimate_duration(transcript: str) -> str:
    """Rough duration estimate based on word count (~150 words/minute)."""
    words = len(transcript.split())
    minutes = max(1, round(words / 150))
    return f"~{minutes} minute{'s' if minutes != 1 else ''}"


def build_incident_form(data: dict) -> dict:
    """Read the transcript, have AI fill the form, and return the full document.

    Parameters
    ----------
    data : dict
        Validated request payload (contains transcript + optional metadata).

    Returns
    -------
    dict
        The completed incident form with confidence scores.
    """
    now = datetime.now(timezone.utc)
    form_id = str(uuid.uuid4())
    transcript_text = data["transcript"]

    # AI reads the transcript and fills out all form fields
    ai_fields = _ai_fill_form(transcript_text)
    ai_fields = _apply_transcript_heuristics(ai_fields, transcript_text)
    ai_fields["steps_taken"] = _sanitize_steps_taken(
        transcript_text,
        ai_fields.get("steps_taken", []),
    )
    if not ai_fields["steps_taken"]:
        ai_fields["steps_taken_confidence"] = "low"

    metadata = data.get("metadata", {}) or {}
    overrides = {
        "caller_name": metadata.get("caller_name") or metadata.get("name"),
        "account_or_reference": metadata.get("account_or_reference") or metadata.get("account"),
        "contact_info": metadata.get("contact_info") or metadata.get("contact"),
    }
    for field, value in overrides.items():
        if isinstance(value, str) and value.strip():
            ai_fields[field] = value.strip()
            ai_fields[f"{field}_confidence"] = "high"

    # Safety pass to redact blocked terms from high-visibility fields.
    ai_fields = _apply_content_filter(ai_fields, metadata)

    # Extract confidence ratings
    confidence = _extract_confidence(ai_fields)

    form = {
        "form_id": form_id,
        "completed_at": now.isoformat(),
        "status": "completed",

        # --- Caller Information (filled by AI) ---
        "caller_information": {
            "name": ai_fields.get("caller_name", "Not mentioned"),
            "account_or_reference": ai_fields.get("account_or_reference", "Not mentioned"),
            "contact_info": ai_fields.get("contact_info", "Not mentioned"),
        },

        # --- Call Details ---
        "call_details": {
            "date": (
                data["call_date"].isoformat() if data.get("call_date") else now.isoformat()
            ),
            "agent_name": ai_fields.get("agent_name", "Not mentioned"),
            "duration_estimate": _estimate_duration(transcript_text),
        },

        # --- Issue (filled by AI) ---
        "issue": {
            "category": ai_fields.get("issue_category", "General"),
            "priority": ai_fields.get("issue_priority", "Medium"),
            "description": ai_fields.get("issue_description", ""),
            "error_messages": ai_fields.get("error_messages", "None"),
        },

        # --- Resolution (filled by AI) ---
        "resolution": {
            "status": ai_fields.get("resolution_status", "Unresolved"),
            "steps_taken": ai_fields.get("steps_taken", []),
            "outcome": ai_fields.get("resolution_outcome", ""),
        },

        # --- Follow-up (filled by AI) ---
        "follow_up": {
            "required": ai_fields.get("follow_up_required", False),
            "actions": ai_fields.get("follow_up_actions", []),
            "department": ai_fields.get("follow_up_department", "None"),
        },

        # --- Overall assessment (filled by AI) ---
        "customer_sentiment": ai_fields.get("customer_sentiment", "Neutral"),
        "call_summary": ai_fields.get("call_summary", ""),

        # --- AI Confidence ---
        "confidence": confidence,

        # --- Raw transcript for reference ---
        "transcript": {
            "full_text": transcript_text,
            "word_count": len(transcript_text.split()),
        },

        "metadata": data.get("metadata", {}),
    }

    include_dutch_translation = _as_bool(
        metadata.get("include_dutch_translation"),
        default=DEFAULT_INCLUDE_DUTCH_TRANSLATION,
    )

    if include_dutch_translation:
        # Only translate short summary fields — NOT the full transcript.
        # Full transcript translation is the #1 cause of timeouts on CPU.
        dutch_summary = _translate_text_to_dutch(str(form.get("call_summary", "")))
        dutch_description = _translate_text_to_dutch(
            str(form.get("issue", {}).get("description", ""))
        )
        form["translated_nl"] = {
            "language": "nl",
            "transcript_text": dutch_summary,
            "call_summary": dutch_summary,
            "issue_description": dutch_description,
        }

    return form
