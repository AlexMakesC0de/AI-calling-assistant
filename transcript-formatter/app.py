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
import uuid
from datetime import datetime, timezone

import requests as http_client
from flask import Flask, jsonify, request
from marshmallow import Schema, fields, validate, ValidationError

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

app = Flask(__name__)
app.config["TEMPLATE_DIR"] = os.getenv("TEMPLATE_DIR", "/data/shared/templates")

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s – %(message)s",
)
logger = logging.getLogger(__name__)

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
        prompt = _FORM_FILL_PROMPT.format(transcript=transcript)
        resp = http_client.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.2},
            },
            timeout=180,
        )
        resp.raise_for_status()
        raw_response = resp.json().get("response", "")
        logger.info("Ollama raw response length: %d chars", len(raw_response))

        # Strip markdown fences if the model wraps the JSON
        cleaned = raw_response.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

        result = json.loads(cleaned)
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
    return jsonify(form), 200


# ---------------------------------------------------------------------------
# Entrypoint (development only – production uses gunicorn)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
