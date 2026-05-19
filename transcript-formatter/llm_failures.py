"""
Dedicated rotating-file logger for failed LLM extractions.

When a model output cannot be used (JSON parse error or schema validation
failure) we capture the full prompt + raw response in a separate log file so
prompt drift can be debugged without trawling the service log. PII that the
prototype handles — caller name, agent name, contact info — is masked in
both the parsed response and inside common "my name is …" patterns in the
prompt before write, so the failure log is safer to share than the raw
transcript.
"""

import json
import logging
import os
import re
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path

import requests

LLM_FAILURE_LOG_PATH = Path(
    os.getenv(
        "LLM_FAILURE_LOG_PATH",
        "/data/shared/logs/transcript-formatter/llm-failures.log",
    )
)
LLM_FAILURE_LOG_MAX_BYTES = int(
    os.getenv("LLM_FAILURE_LOG_MAX_BYTES", str(10 * 1024 * 1024))
)
LLM_FAILURE_LOG_BACKUP_COUNT = int(os.getenv("LLM_FAILURE_LOG_BACKUP_COUNT", "5"))

EMAIL_URL = os.getenv("EMAIL_URL", "http://email-sender:5002/send")
ENGINEER_ALERT_EMAIL = os.getenv(
    "ENGINEER_ALERT_EMAIL",
    os.getenv("SUPPORT_EMAIL", "support-team@example.com"),
)
ENGINEER_ALERT_TIMEOUT = float(os.getenv("ENGINEER_ALERT_TIMEOUT", "5"))

_logger = logging.getLogger(__name__)
_failure_logger: logging.Logger | None = None

_NAME_INTRO_PATTERNS = [
    re.compile(
        r"\b(my name is|this is|i am|i'm)\s+([A-Z][a-zA-Z'\-]+(?:\s+[A-Z][a-zA-Z'\-]+)?)",
        re.IGNORECASE,
    ),
]

_NAME_FIELDS = ("caller_name", "agent_name", "contact_info")
_NEUTRAL_VALUES = {"", "not mentioned", "none"}


def _setup_failure_logger() -> logging.Logger | None:
    try:
        LLM_FAILURE_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(
            LLM_FAILURE_LOG_PATH,
            maxBytes=LLM_FAILURE_LOG_MAX_BYTES,
            backupCount=LLM_FAILURE_LOG_BACKUP_COUNT,
            encoding="utf-8",
        )
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger = logging.getLogger("transcript_formatter.llm_failures")
        logger.setLevel(logging.INFO)
        logger.propagate = False
        logger.addHandler(handler)
        return logger
    except Exception:
        _logger.exception(
            "Could not initialise LLM failure log at %s; failures will only "
            "appear on the service log.",
            LLM_FAILURE_LOG_PATH,
        )
        return None


def _get_failure_logger() -> logging.Logger | None:
    global _failure_logger
    if _failure_logger is not None:
        return _failure_logger
    _failure_logger = _setup_failure_logger()
    return _failure_logger


def _mask_names_in_text(text: str) -> str:
    if not text:
        return text
    result = text
    for pattern in _NAME_INTRO_PATTERNS:
        result = pattern.sub(
            lambda m: f"{m.group(1)} [NAME REDACTED]", result
        )
    return result


def _mask_parsed_response(payload):
    if not isinstance(payload, dict):
        return payload
    masked = dict(payload)
    for field in _NAME_FIELDS:
        value = masked.get(field)
        if isinstance(value, str) and value.strip().lower() not in _NEUTRAL_VALUES:
            masked[field] = "[REDACTED]"
    return masked


def log_llm_failure(
    *,
    reason: str,
    model: str,
    prompt: str,
    raw_response: str,
    parsed_response=None,
    schema_errors=None,
    request_id: str | None = None,
) -> None:
    """Append one structured JSON entry describing a failed LLM extraction."""
    try:
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "reason": reason,
            "model": model,
            "request_id": request_id,
            "prompt": _mask_names_in_text(prompt or ""),
            "raw_response": raw_response or "",
            "parsed_response": _mask_parsed_response(parsed_response),
            "schema_errors": schema_errors,
        }
        line = json.dumps(record, ensure_ascii=False, default=str)
    except Exception:
        _logger.exception("Failed to serialise LLM failure record")
        return

    failure_logger = _get_failure_logger()
    if failure_logger is None:
        _logger.warning("LLM failure (no dedicated log available): %s", line)
        return
    failure_logger.info(line)


def notify_engineer_extraction_failed(
    *,
    model: str,
    initial_errors,
    retry_errors,
    request_id: str | None = None,
) -> bool:
    """POST an alert to the email-sender so an engineer reviews the form.

    Returns True when the email-sender accepted the request, False otherwise.
    Network or remote failures never raise — the formatter still has to
    return a placeholder response to the caller.
    """
    subject = "[Transcript Formatter] AI extraction failed — engineer review required"
    body_lines = [
        "The transcript formatter could not extract a valid incident form from",
        "this call. Both the initial LLM attempt and the clarifying retry",
        "returned responses that failed schema validation.",
        "",
        f"Model: {model}",
    ]
    if request_id:
        body_lines.append(f"Request ID: {request_id}")
    body_lines.extend([
        "",
        "Schema errors (initial attempt):",
        json.dumps(initial_errors, indent=2, default=str),
        "",
        "Schema errors (retry attempt):",
        json.dumps(retry_errors, indent=2, default=str),
        "",
        f"Full prompts and raw responses are in {LLM_FAILURE_LOG_PATH}.",
        "Please open the case in the dashboard and complete the form manually.",
    ])

    payload = {
        "to": ENGINEER_ALERT_EMAIL,
        "subject": subject,
        "body": "\n".join(body_lines),
        "html": False,
    }

    try:
        resp = requests.post(
            EMAIL_URL, json=payload, timeout=ENGINEER_ALERT_TIMEOUT,
        )
        resp.raise_for_status()
    except Exception as exc:
        _logger.warning(
            "Engineer alert email could not be sent to %s via %s: %s",
            ENGINEER_ALERT_EMAIL, EMAIL_URL, exc,
        )
        return False

    _logger.info(
        "Engineer alert email dispatched to %s for failed AI extraction",
        ENGINEER_ALERT_EMAIL,
    )
    return True
