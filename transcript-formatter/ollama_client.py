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
from llm_failures import log_llm_failure, notify_engineer_extraction_failed
from schemas import validate_llm_response

PLACEHOLDER_MESSAGE = "AI extraction failed - engineer review required"

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


def _placeholder_form_fill() -> dict:
    """Return a clearly-marked placeholder form for engineer review.

    Used when both the initial LLM call and the retry fail schema
    validation. ``extraction_failed`` is set to True so downstream
    consumers can route the case for manual review, and every
    confidence score is "low".
    """
    result = {
        "caller_name": "Not mentioned",
        "account_or_reference": "Not mentioned",
        "contact_info": "Not mentioned",
        "agent_name": "Not mentioned",
        "issue_category": "General",
        "issue_priority": "Medium",
        "issue_description": PLACEHOLDER_MESSAGE,
        "error_messages": "None",
        "resolution_status": "Unresolved",
        "steps_taken": [],
        "resolution_outcome": PLACEHOLDER_MESSAGE,
        "follow_up_required": True,
        "follow_up_actions": ["Engineer review required"],
        "follow_up_department": "None",
        "customer_sentiment": "Neutral",
        "call_summary": PLACEHOLDER_MESSAGE,
        "extraction_failed": True,
    }
    for field in SCORED_FIELDS:
        result[f"{field}_confidence"] = "low"
    return result


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


def _call_llm_and_validate(
    prompt: str, model_name: str, *, attempt: str,
) -> tuple[dict | None, dict | None]:
    """Send one prompt to Ollama and try to parse + validate the response.

    Returns ``(result, errors)``:
        * ``result`` is the parsed+validated dict on success, ``None`` on
          schema validation failure.
        * ``errors`` is the marshmallow error dict when validation failed,
          otherwise ``None``.

    JSON parse / network errors are logged to the failure log and raised so
    the caller can decide whether to retry. ``attempt`` is "initial" or
    "retry" and is used in failure-log reasons + service-log lines.
    """
    logger.info(
        "Sending LLM extraction %s prompt (%d chars) to model %s",
        attempt, len(prompt), model_name,
    )
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
    logger.info("Ollama %s response length: %d chars", attempt, len(raw_response))

    cleaned = _strip_markdown_fences(raw_response)
    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError:
        extracted = _extract_json_object(cleaned)
        if not extracted:
            log_llm_failure(
                reason=f"json_parse_{attempt}",
                model=model_name,
                prompt=prompt,
                raw_response=raw_response,
            )
            raise
        try:
            result = json.loads(extracted)
        except json.JSONDecodeError:
            log_llm_failure(
                reason=f"json_parse_{attempt}",
                model=model_name,
                prompt=prompt,
                raw_response=raw_response,
            )
            raise

    validate_start = time.monotonic()
    is_valid, errors = validate_llm_response(result)
    validate_ms = (time.monotonic() - validate_start) * 1000
    logger.info("LLM %s response schema validation took %.1fms", attempt, validate_ms)

    if not is_valid:
        logger.warning(
            "LLM %s response failed schema validation: %s", attempt, errors,
        )
        log_llm_failure(
            reason=f"schema_validation_{attempt}",
            model=model_name,
            prompt=prompt,
            raw_response=raw_response,
            parsed_response=result,
            schema_errors=errors,
        )
        return None, errors

    return result, None


def _build_retry_prompt(original_prompt: str, schema_errors: dict) -> str:
    """Build a clarifying retry prompt from schema validation errors."""
    lines: list[str] = []
    for field, messages in schema_errors.items():
        if isinstance(messages, list):
            joined = "; ".join(str(m) for m in messages)
        else:
            joined = str(messages)
        lines.append(f"- {field}: {joined}")
    issue_block = "\n".join(lines) if lines else "- (schema mismatch)"

    prefix = (
        "Your previous response did not match the required JSON schema. "
        "These fields failed validation:\n"
        f"{issue_block}\n\n"
        "Return ONLY a single JSON object with EVERY required key present "
        "and using the exact enum values allowed. Do not add markdown "
        "fences, commentary, or extra text outside the JSON object.\n\n"
    )
    return prefix + original_prompt


def _ai_fill_form(transcript: str) -> dict:
    """Send the transcript to Ollama and get back the filled form fields.

    On schema validation failure, retry exactly once with a clarifying
    prefix added to the original prompt, using the same model. Falls back
    to a basic extraction if both attempts fail or the LLM is unreachable.
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

        result, initial_errors = _call_llm_and_validate(
            prompt, model_name, attempt="initial",
        )
        if result is not None:
            return result

        retry_prompt = _build_retry_prompt(prompt, initial_errors or {})
        logger.info("Retrying LLM extraction with clarifying prompt")
        retry_result, retry_errors = _call_llm_and_validate(
            retry_prompt, model_name, attempt="retry",
        )
        if retry_result is not None:
            logger.info("LLM retry succeeded after initial validation failure")
            return retry_result

        # Both attempts validated as broken — flag the case, notify an
        # engineer, and return a placeholder so the pipeline keeps moving.
        logger.warning(
            "LLM retry also failed schema validation; returning placeholder",
        )
        notify_engineer_extraction_failed(
            model=model_name,
            initial_errors=initial_errors,
            retry_errors=retry_errors,
        )
        return _placeholder_form_fill()

    except Exception as exc:
        # Network / unrecoverable JSON errors fall back to the canned
        # extraction rather than the engineer-review placeholder, since the
        # LLM itself was never reached or returned nothing usable.
        logger.warning("AI form-fill failed, using fallback: %s", exc)
        return _fallback_form_fill(transcript)
