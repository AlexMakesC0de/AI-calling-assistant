"""
Transcript Formatter Service
=============================
Receives raw transcript text via POST /format, uses a local LLM (Ollama)
to read the transcript and fill out a structured incident form, then
returns the completed form as JSON.

The AI acts like a support analyst — it reads the conversation and extracts
all the information needed to complete the form fields automatically.
It also rates its confidence for each field it fills.
"""

import json
import logging
import os
import re
import time
import uuid
from datetime import datetime, timezone

import requests as http_client
from flask import Flask, jsonify, request
from marshmallow import Schema, fields, validate, ValidationError

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

app = Flask(__name__)
# Ensure Flask produces UTF-8 JSON output without escaping non-ASCII characters.
# This makes Russian (and other non-latin) text readable in responses.
app.config["JSON_AS_ASCII"] = False
app.config["TEMPLATE_DIR"] = os.getenv("TEMPLATE_DIR", "/data/shared/templates")

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
OLLAMA_CONNECT_TIMEOUT = float(os.getenv("OLLAMA_CONNECT_TIMEOUT", "3"))
OLLAMA_READ_TIMEOUT = float(os.getenv("OLLAMA_READ_TIMEOUT", "120"))
OLLAMA_TRANSLATE_READ_TIMEOUT = float(
    os.getenv("OLLAMA_TRANSLATE_READ_TIMEOUT", str(max(OLLAMA_READ_TIMEOUT, 120.0)))
)
OLLAMA_PULL_TIMEOUT = float(os.getenv("OLLAMA_PULL_TIMEOUT", "900"))
TRANSLATION_TIME_BUDGET = float(os.getenv("TRANSLATION_TIME_BUDGET", "240"))
TERM_FILTER_MODE = os.getenv("TERM_FILTER_MODE", "basic").strip().lower()
TERM_FILTER_CUSTOM_WORDS = os.getenv("TERM_FILTER_CUSTOM_WORDS", "")
TERM_FILTER_REPLACEMENT = os.getenv("TERM_FILTER_REPLACEMENT", "[redacted]")
TRANSLATION_CHUNK_MAX_CHARS = int(os.getenv("TRANSLATION_CHUNK_MAX_CHARS", "2500"))
DEFAULT_INCLUDE_DUTCH_TRANSLATION = os.getenv(
    "DEFAULT_INCLUDE_DUTCH_TRANSLATION", "true"
).strip().lower() in ("1", "true", "yes", "on")

_BASIC_FILTER_TERMS = {
    "nigger",
    "nigga",
    "faggot",
    "retard",
    "whore",
    "slut",
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s – %(message)s",
)
logger = logging.getLogger(__name__)

_ACTIVE_OLLAMA_MODEL: str | None = None

# ---------------------------------------------------------------------------
# Request Schema
# ---------------------------------------------------------------------------


class FormatRequestSchema(Schema):
    """Validates the incoming POST body."""

    transcript = fields.String(
        required=True,
        validate=validate.Length(min=1),
        metadata={"description": "Raw transcript text from the call."},
    )
    call_date = fields.DateTime(load_default=None)
    metadata = fields.Dict(keys=fields.String(), load_default={})


format_request_schema = FormatRequestSchema()

# ---------------------------------------------------------------------------
# AI Prompt — instructs the LLM to fill out the incident form with
# confidence scoring for each field
# ---------------------------------------------------------------------------

_FORM_FILL_PROMPT = """\
You are an experienced customer-support analyst. You have just received a \
transcript of a support call. The transcript uses speaker diarization — each \
line is prefixed with a speaker label such as "Speaker 1:" or "Speaker 2:". \
In most calls, the person who speaks first is the support agent (they greet \
the caller), and the other speaker is the customer/caller. Use these labels \
to accurately identify who said what.

The transcript may be in English, Dutch, or another language. If needed, \
translate internally while extracting data, but keep the final JSON values in \
clear English (except proper names, product names, and exact error text).

Your job is to read through the conversation \
and fill out the incident form below by extracting the relevant information \
from the transcript.

Fill out EVERY field as accurately as possible based on what was said in the \
call. If information for a field was not mentioned, write "Not mentioned" for \
string fields or use your best judgement for enum fields.

For each field, also rate your CONFIDENCE as "high", "medium", or "low":
- "high" = the information was explicitly stated in the transcript
- "medium" = you inferred it from context
- "low" = it was not mentioned and you are guessing

Return ONLY a valid JSON object with EXACTLY these keys (no markdown fences, \
no extra text, no explanation):

{{
  "caller_name": "<caller's name or 'Not mentioned'>",
  "caller_name_confidence": "<high|medium|low>",
  "account_or_reference": "<any account/customer ID/reference number or 'Not mentioned'>",
  "account_or_reference_confidence": "<high|medium|low>",
  "contact_info": "<phone or email if mentioned, or 'Not mentioned'>",
  "contact_info_confidence": "<high|medium|low>",
  "agent_name": "<support agent's name or 'Not mentioned'>",
  "agent_name_confidence": "<high|medium|low>",
  "issue_category": "<one of: Technical, Billing, Account, Shipping, Network, Software, Hardware, General>",
  "issue_category_confidence": "<high|medium|low>",
  "issue_priority": "<one of: Low, Medium, High, Critical>",
  "issue_priority_confidence": "<high|medium|low>",
  "issue_description": "<clear description of the caller's problem>",
  "issue_description_confidence": "<high|medium|low>",
  "error_messages": "<any specific error messages/codes mentioned or 'None'>",
  "error_messages_confidence": "<high|medium|low>",
  "resolution_status": "<one of: Resolved, Partially Resolved, Unresolved, Escalated>",
  "resolution_status_confidence": "<high|medium|low>",
  "steps_taken": ["<step 1>", "<step 2>"],
  "steps_taken_confidence": "<high|medium|low>",
  "resolution_outcome": "<what was the final result of the call>",
  "resolution_outcome_confidence": "<high|medium|low>",
  "follow_up_required": true or false,
  "follow_up_required_confidence": "<high|medium|low>",
  "follow_up_actions": ["<action 1>"] or [],
  "follow_up_actions_confidence": "<high|medium|low>",
  "follow_up_department": "<department to escalate to, or 'None'>",
  "follow_up_department_confidence": "<high|medium|low>",
  "customer_sentiment": "<one of: Very Satisfied, Satisfied, Neutral, Dissatisfied, Very Dissatisfied>",
  "customer_sentiment_confidence": "<high|medium|low>",
  "call_summary": "<2-3 sentence summary of the entire call>",
  "call_summary_confidence": "<high|medium|low>"
}}

TRANSCRIPT:
{transcript}
"""

# Fields that have confidence scores
_SCORED_FIELDS = [
    "caller_name", "account_or_reference", "contact_info", "agent_name",
    "issue_category", "issue_priority", "issue_description", "error_messages",
    "resolution_status", "steps_taken", "resolution_outcome",
    "follow_up_required", "follow_up_actions", "follow_up_department",
    "customer_sentiment", "call_summary",
]

_NON_ACTION_STEP_PATTERNS = [
    r"^\s*(hi|hello|hey|good\s+(morning|afternoon|evening))\b",
    r"\bmy name is\b",
    r"\bthis is\b",
    r"\bi am\b",
    r"\bi'm\b",
    r"\bcan you help me\b",
    r"\bplease help\b",
    r"\bi need help\b",
]

_ACTION_HINT_PATTERNS = [
    r"\b(check(ed)?|verify|verified|diagnos(ed|is)|troubleshoot(ed|ing)?)\b",
    r"\b(reset|restart(ed)?|reboot(ed)?|reinstall(ed)?|configur(ed|ing))\b",
    r"\b(ask(ed)?|instruct(ed|ion)|advis(ed|e)|guid(ed|ance)|walk(ed)?\s+through)\b",
    r"\b(escalat(ed|e)|open(ed)?\s+(a\s+)?(ticket|case)|creat(ed)?\s+(a\s+)?(ticket|case))\b",
    r"\b(test(ed|ing)?|collect(ed)?|updat(ed|ing)?|provid(ed|ing)?)\b",
]


def _parse_custom_terms(raw: str) -> set[str]:
    terms = set()
    for part in raw.split(","):
        term = part.strip().lower()
        if term:
            terms.add(term)
    return terms


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
        return set(_BASIC_FILTER_TERMS)

    # custom mode
    custom_from_metadata = str(metadata.get("term_filter_custom_words") or "")
    source = custom_from_metadata if custom_from_metadata.strip() else TERM_FILTER_CUSTOM_WORDS
    return _parse_custom_terms(source)


def _sanitize_text_value(value: str, blocked_terms: set[str], replacement: str) -> tuple[str, bool]:
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


def _ollama_list_models() -> list[str]:
    try:
        resp = http_client.get(
            f"{OLLAMA_URL}/api/tags",
            timeout=(OLLAMA_CONNECT_TIMEOUT, OLLAMA_READ_TIMEOUT),
        )
        resp.raise_for_status()
        models = resp.json().get("models", [])
        names: list[str] = []
        for m in models:
            name = str(m.get("name") or "").strip()
            if name:
                names.append(name)
        return names
    except Exception as exc:
        logger.warning("Could not list Ollama models: %s", exc)
        return []


def _pull_ollama_model(model_name: str) -> bool:
    try:
        logger.info("Pulling missing Ollama model: %s", model_name)
        resp = http_client.post(
            f"{OLLAMA_URL}/api/pull",
            json={"name": model_name, "stream": False},
            timeout=(OLLAMA_CONNECT_TIMEOUT, OLLAMA_PULL_TIMEOUT),
        )
        resp.raise_for_status()
        return True
    except Exception as exc:
        logger.warning("Failed to pull Ollama model %s: %s", model_name, exc)
        return False


def _resolve_ollama_model() -> str:
    global _ACTIVE_OLLAMA_MODEL

    if _ACTIVE_OLLAMA_MODEL:
        return _ACTIVE_OLLAMA_MODEL

    available = _ollama_list_models()
    if OLLAMA_MODEL in available:
        _ACTIVE_OLLAMA_MODEL = OLLAMA_MODEL
        return _ACTIVE_OLLAMA_MODEL

    if OLLAMA_MODEL and _pull_ollama_model(OLLAMA_MODEL):
        _ACTIVE_OLLAMA_MODEL = OLLAMA_MODEL
        return _ACTIVE_OLLAMA_MODEL

    available = _ollama_list_models()
    if available:
        _ACTIVE_OLLAMA_MODEL = available[0]
        logger.warning(
            "Configured model %s unavailable, falling back to %s",
            OLLAMA_MODEL,
            _ACTIVE_OLLAMA_MODEL,
        )
        return _ACTIVE_OLLAMA_MODEL

    _ACTIVE_OLLAMA_MODEL = OLLAMA_MODEL
    return _ACTIVE_OLLAMA_MODEL


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
    for pattern in _NON_ACTION_STEP_PATTERNS:
        if re.search(pattern, text, flags=re.IGNORECASE):
            return True
    return False


def _looks_actionable_step(step: str) -> bool:
    """Return True when text looks like an agent action."""
    text = step.strip()
    if not text or _is_non_action_step(text):
        return False
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in _ACTION_HINT_PATTERNS)


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


def _extract_confidence(ai_fields: dict) -> dict:
    """Pull confidence ratings out of the AI response into a summary.

    Returns a dict with:
      - per_field:  { field_name: "high"|"medium"|"low", ... }
      - overall:    "High" | "Medium" | "Low"
      - low_confidence_fields:  list of field names rated "low"
    """
    per_field = {}
    for field in _SCORED_FIELDS:
        conf_key = f"{field}_confidence"
        conf = ai_fields.get(conf_key, "medium").lower()
        if conf not in ("high", "medium", "low"):
            conf = "medium"
        per_field[field] = conf

    # Compute overall score
    scores = {"high": 3, "medium": 2, "low": 1}
    total = sum(scores.get(v, 2) for v in per_field.values())
    avg = total / len(per_field) if per_field else 2

    if avg >= 2.5:
        overall = "High"
    elif avg >= 1.5:
        overall = "Medium"
    else:
        overall = "Low"

    low_fields = [f for f, v in per_field.items() if v == "low"]

    return {
        "per_field": per_field,
        "overall": overall,
        "low_confidence_fields": low_fields,
    }


def _ai_fill_form(transcript: str) -> dict:
    """Send the transcript to Ollama and get back the filled form fields.

    Falls back to a basic extraction if the LLM is unreachable.
    """
    try:
        # Truncate very long transcripts for form-fill to keep Ollama fast.
        # Keep first 1500 + last 500 chars so start (greetings/names) and
        # end (resolution/farewell) are preserved.
        trimmed = transcript
        if len(transcript) > 2500:
            trimmed = transcript[:1500] + "\n[...middle trimmed...]\n" + transcript[-500:]
            logger.info("Trimmed transcript from %d to %d chars for form-fill.",
                        len(transcript), len(trimmed))
        prompt = _FORM_FILL_PROMPT.format(transcript=trimmed)
        model_name = _resolve_ollama_model()
        resp = http_client.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": model_name,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.2, "num_predict": 800},
            },
            timeout=(OLLAMA_CONNECT_TIMEOUT, OLLAMA_READ_TIMEOUT),
        )
        resp.raise_for_status()
        raw_response = resp.json().get("response", "")
        logger.info("Ollama raw response length: %d chars", len(raw_response))

        cleaned = _strip_markdown_fences(raw_response)
        try:
            result = json.loads(cleaned)
        except json.JSONDecodeError:
            extracted = _extract_json_object(cleaned)
            if not extracted:
                raise
            result = json.loads(extracted)
        return result

    except Exception as exc:
        logger.warning("AI form-fill failed, using fallback: %s", exc)
        return _fallback_form_fill(transcript)


def _fallback_form_fill(transcript: str) -> dict:
    """Basic extraction when the LLM is unavailable."""
    sentences = transcript.replace("!", ".").replace("?", ".").split(".")
    sentences = [s.strip() for s in sentences if s.strip()]
    summary = ". ".join(sentences[:3]) + "." if sentences else "No summary available."

    result = {
        "caller_name": "Not mentioned",
        "account_or_reference": "Not mentioned",
        "contact_info": "Not mentioned",
        "agent_name": "Not mentioned",
        "issue_category": "General",
        "issue_priority": "Medium",
        "issue_description": summary,
        "error_messages": "None",
        "resolution_status": "Unresolved",
        "steps_taken": [],
        "resolution_outcome": "Unable to determine — AI unavailable.",
        "follow_up_required": True,
        "follow_up_actions": ["Review transcript manually"],
        "follow_up_department": "None",
        "customer_sentiment": "Neutral",
        "call_summary": summary,
    }
    # Add low confidence for all fields (fallback = no AI)
    for field in _SCORED_FIELDS:
        result[f"{field}_confidence"] = "low"
    return result


def _strip_markdown_fences(text: str) -> str:
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()
    return cleaned


def _extract_json_object(text: str) -> str | None:
    """Best-effort extraction of first top-level JSON object from model output."""
    if not text:
        return None
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    for idx in range(start, len(text)):
        ch = text[idx]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start: idx + 1]
    return None


def _looks_like_translation_refusal(text: str) -> bool:
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
    return re.sub(r"[^a-z0-9]+", "", (text or "").strip().lower())


def _as_bool(value: object, default: bool = True) -> bool:
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


# ---------------------------------------------------------------------------
# Build the completed incident form
# ---------------------------------------------------------------------------


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


def _estimate_duration(transcript: str) -> str:
    """Rough duration estimate based on word count (~150 words/minute)."""
    words = len(transcript.split())
    minutes = max(1, round(words / 150))
    return f"~{minutes} minute{'s' if minutes != 1 else ''}"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.route("/health", methods=["GET"])
def health():
    """Liveness / readiness probe."""
    return jsonify({"status": "ok"}), 200


@app.route("/format", methods=["POST"])
def format_transcript():
    """Accept a transcript and return a completed incident form.

    **Request (JSON)**::

        {
            "transcript": "Agent: Hello ... Caller: Hi, I have a problem ...",
            "call_date": "2026-03-05T10:30:00Z",   // optional
            "metadata": {}                           // optional
        }

    **Response (JSON)**: A fully completed incident form with all fields
    extracted by AI from the transcript, plus confidence scores.
    """
    json_body = request.get_json(silent=True)
    if json_body is None:
        return jsonify({"error": "Request body must be valid JSON."}), 400

    try:
        data = format_request_schema.load(json_body)
    except ValidationError as err:
        logger.warning("Validation error: %s", err.messages)
        return jsonify({"error": "Validation failed.", "details": err.messages}), 422

    form = build_incident_form(data)
    logger.info("Completed incident form %s (confidence: %s)",
                form["form_id"], form["confidence"]["overall"])
    response = jsonify(form)
    response.headers['Content-Language'] = 'en'
    return response, 200


# ---------------------------------------------------------------------------
# Entrypoint (development only – production uses gunicorn)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
