"""Inbound email/content classifier for the voice-app pipeline (ISR-311)."""

import json
import logging
import os
import time
from typing import Any

import requests

logger = logging.getLogger(__name__)

VALID_LABELS = frozenset({"support", "not_support", "unclear"})


def _ollama_settings() -> tuple[str, str, int, int]:
    return (
        os.getenv("OLLAMA_URL", "http://ollama:11434"),
        os.getenv("OLLAMA_MODEL", "llama3.1:8b"),
        int(os.getenv("OLLAMA_CONNECT_TIMEOUT", "3")),
        int(os.getenv("OLLAMA_READ_TIMEOUT", "120")),
    )


def unclear_confidence_threshold() -> float:
    try:
        return float(os.getenv("CLASSIFIER_UNCLEAR_THRESHOLD", "0.55"))
    except ValueError:
        return 0.55


def classify_inbound(content: str) -> dict[str, Any]:
    """
    Classify inbound text as support / not_support / unclear with confidence.

    Returns dict with keys: label, confidence (0-1), reason, duration_ms.
    """
    ollama_url, model, connect_timeout, read_timeout = _ollama_settings()
    prompt = f"""Classify this inbound support message.

{content[:2500]}

Respond with ONLY a JSON object:
{{"label": "support"|"not_support"|"unclear", "confidence": 0.0-1.0, "reason": "brief reason"}}

- support: machine/equipment/service issue needing a support case
- not_support: marketing, newsletters, spam, unrelated mail
- unclear: cannot tell with confidence — use when ambiguous
"""

    started = time.perf_counter()
    try:
        response = requests.post(
            f"{ollama_url}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "temperature": 0.2,
            },
            timeout=(connect_timeout, read_timeout),
        )
        response.raise_for_status()
        response_text = response.json().get("response", "")
        json_start = response_text.find("{")
        json_end = response_text.rfind("}") + 1
        if json_start == -1 or json_end <= json_start:
            raise ValueError("No JSON in classifier response")

        parsed = json.loads(response_text[json_start:json_end])
        label = str(parsed.get("label", "unclear")).lower()
        if label not in VALID_LABELS:
            label = "unclear"
        confidence = float(parsed.get("confidence", 0.5))
        confidence = max(0.0, min(1.0, confidence))
        reason = str(parsed.get("reason", ""))
    except Exception as exc:
        logger.error("Classifier failed: %s", exc)
        label = "unclear"
        confidence = 0.0
        reason = f"Classifier error: {exc}"

    duration_ms = int((time.perf_counter() - started) * 1000)
    result = {
        "label": label,
        "confidence": confidence,
        "reason": reason,
        "duration_ms": duration_ms,
    }
    logger.info(
        "Classification label=%s confidence=%.2f duration_ms=%d",
        label,
        confidence,
        duration_ms,
    )
    return result


def should_create_case(classification: dict[str, Any]) -> bool:
    """Decide whether to proceed to formatter/DB based on label + threshold."""
    label = classification.get("label")
    confidence = float(classification.get("confidence", 0.0))
    if label == "not_support":
        return False
    if label == "support":
        return True
    # unclear — proceed when confidence meets threshold (needs human review)
    return confidence >= unclear_confidence_threshold()
