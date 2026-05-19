"""
Ollama LLM integration for the Transcript Formatter service.
"""

import json
import logging
import os
import time

import requests

from config import (
    OLLAMA_URL,
    OLLAMA_MODEL_DEFAULT,
    OLLAMA_CONNECT_TIMEOUT,
    OLLAMA_READ_TIMEOUT,
    FORM_FILL_PROMPT_TEMPLATE,
    SCORED_FIELDS,
)
from llm_failures import log_llm_failure
from schemas import validate_llm_response

logger = logging.getLogger(__name__)
http_client = requests.Session()

# Models we've already confirmed available (or successfully pulled) since boot.
# OLLAMA_MODEL itself is read fresh from the environment on every request, so
# operators can swap models by updating the env and triggering a graceful
# request cycle — in-flight requests keep the value they captured.
_VERIFIED_MODELS: set[str] = set()


def _ollama_list_models() -> list[str]:
    """List all available models from Ollama."""
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
    """Pull a missing model from Ollama repository."""
    try:
        logger.info("Pulling missing Ollama model: %s", model_name)
        resp = http_client.post(
            f"{OLLAMA_URL}/api/pull",
            json={"name": model_name, "stream": False},
            timeout=(OLLAMA_CONNECT_TIMEOUT, float(
                900  # 15-minute timeout for pulls
            )),
        )
        resp.raise_for_status()
        return True
    except Exception as exc:
        logger.warning("Failed to pull Ollama model %s: %s", model_name, exc)
        return False


def _resolve_ollama_model() -> str:
    """Resolve the active Ollama model name for this request.

    Reads OLLAMA_MODEL fresh per call so operators can change the env var
    between requests and have new requests pick up the new model immediately,
    while any in-flight request keeps the name it already captured.
    """
    requested = os.getenv("OLLAMA_MODEL", OLLAMA_MODEL_DEFAULT)

    if requested in _VERIFIED_MODELS:
        return requested

    available = _ollama_list_models()
    if requested in available:
        _VERIFIED_MODELS.add(requested)
        return requested

    if requested and _pull_ollama_model(requested):
        _VERIFIED_MODELS.add(requested)
        return requested

    available = _ollama_list_models()
    if available:
        fallback = available[0]
        logger.warning(
            "Configured model %s unavailable, falling back to %s",
            requested,
            fallback,
        )
        _VERIFIED_MODELS.add(fallback)
        return fallback

    return requested


def _strip_markdown_fences(text: str) -> str:
    """Remove markdown code fences from text."""
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
    for field in SCORED_FIELDS:
        result[f"{field}_confidence"] = "low"
    return result


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
        prompt = FORM_FILL_PROMPT_TEMPLATE.replace("{TRANSCRIPT}", trimmed)
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
                log_llm_failure(
                    reason="json_parse",
                    model=model_name,
                    prompt=prompt,
                    raw_response=raw_response,
                )
                raise
            try:
                result = json.loads(extracted)
            except json.JSONDecodeError:
                log_llm_failure(
                    reason="json_parse",
                    model=model_name,
                    prompt=prompt,
                    raw_response=raw_response,
                )
                raise

        validate_start = time.monotonic()
        is_valid, errors = validate_llm_response(result)
        validate_ms = (time.monotonic() - validate_start) * 1000
        logger.info("LLM response schema validation took %.1fms", validate_ms)
        if not is_valid:
            logger.warning(
                "LLM response failed schema validation: %s", errors,
            )
            log_llm_failure(
                reason="schema_validation",
                model=model_name,
                prompt=prompt,
                raw_response=raw_response,
                parsed_response=result,
                schema_errors=errors,
            )
            raise ValueError("LLM response did not match expected schema")

        return result

    except Exception as exc:
        logger.warning("AI form-fill failed, using fallback: %s", exc)
        return _fallback_form_fill(transcript)
