"""Tests for schema validation (Sprint3#16).

Covers:
  Sprint3#16  Map Transcript to Incident Schema — all fields populated or defaulted
"""

from __future__ import annotations

from marshmallow import ValidationError

from schemas import (
    CONFIDENCE_VALUES,
    CUSTOMER_SENTIMENTS,
    ISSUE_CATEGORIES,
    ISSUE_PRIORITIES,
    RESOLUTION_STATUSES,
    format_request_schema,
    validate_llm_response,
)


def _valid_llm_payload() -> dict:
    return {
        "caller_name": "Jan de Vries",
        "caller_name_confidence": "high",
        "account_or_reference": "AC-12345",
        "account_or_reference_confidence": "high",
        "contact_info": "jan@example.com",
        "contact_info_confidence": "medium",
        "agent_name": "Femke",
        "agent_name_confidence": "high",
        "issue_category": "Technical",
        "issue_category_confidence": "high",
        "issue_priority": "High",
        "issue_priority_confidence": "medium",
        "issue_description": "Printer on floor 2 is not responding.",
        "issue_description_confidence": "high",
        "error_messages": "ERR-204",
        "error_messages_confidence": "medium",
        "resolution_status": "Unresolved",
        "resolution_status_confidence": "high",
        "steps_taken": ["Checked printer connection", "Restarted printer"],
        "steps_taken_confidence": "high",
        "resolution_outcome": "Escalated to hardware team.",
        "resolution_outcome_confidence": "medium",
        "follow_up_required": True,
        "follow_up_required_confidence": "high",
        "follow_up_actions": ["Send technician to floor 2"],
        "follow_up_actions_confidence": "medium",
        "follow_up_department": "Hardware Support",
        "follow_up_department_confidence": "medium",
        "customer_sentiment": "Dissatisfied",
        "customer_sentiment_confidence": "high",
        "call_summary": "Customer reported a non-responsive printer on floor 2.",
        "call_summary_confidence": "high",
    }


# ---------------------------------------------------------------------------
# FormatRequestSchema
# ---------------------------------------------------------------------------

def test_format_request_requires_transcript():
    try:
        format_request_schema.load({})
        assert False, "Should have raised"
    except ValidationError as exc:
        assert "transcript" in exc.messages


def test_format_request_rejects_empty_transcript():
    try:
        format_request_schema.load({"transcript": ""})
        assert False, "Should have raised"
    except ValidationError as exc:
        assert "transcript" in exc.messages


def test_format_request_accepts_minimal():
    data = format_request_schema.load({"transcript": "hello"})
    assert data["transcript"] == "hello"
    assert data["metadata"] == {}


def test_format_request_preserves_metadata():
    data = format_request_schema.load({
        "transcript": "hello",
        "metadata": {"redact_pii": False, "custom_key": "value"},
    })
    assert data["metadata"]["redact_pii"] is False


def test_format_request_excludes_unknown_top_level():
    data = format_request_schema.load({
        "transcript": "hello",
        "unknown_field": "dropped",
    })
    assert "unknown_field" not in data


# ---------------------------------------------------------------------------
# LLM response validation — Sprint3#16 core
# ---------------------------------------------------------------------------

def test_valid_payload_passes():
    is_valid, errors = validate_llm_response(_valid_llm_payload())
    assert is_valid is True
    assert errors == {}


def test_missing_required_field_fails():
    payload = _valid_llm_payload()
    del payload["caller_name"]
    is_valid, errors = validate_llm_response(payload)
    assert is_valid is False
    assert "caller_name" in errors


def test_invalid_category_fails():
    payload = _valid_llm_payload()
    payload["issue_category"] = "MaybeBilling"
    is_valid, errors = validate_llm_response(payload)
    assert is_valid is False
    assert "issue_category" in errors


def test_invalid_priority_fails():
    payload = _valid_llm_payload()
    payload["issue_priority"] = "Urgent"
    is_valid, errors = validate_llm_response(payload)
    assert is_valid is False
    assert "issue_priority" in errors


def test_invalid_resolution_status_fails():
    payload = _valid_llm_payload()
    payload["resolution_status"] = "InProgress"
    is_valid, errors = validate_llm_response(payload)
    assert is_valid is False
    assert "resolution_status" in errors


def test_invalid_sentiment_fails():
    payload = _valid_llm_payload()
    payload["customer_sentiment"] = "Angry"
    is_valid, errors = validate_llm_response(payload)
    assert is_valid is False
    assert "customer_sentiment" in errors


def test_invalid_confidence_value_fails():
    payload = _valid_llm_payload()
    payload["caller_name_confidence"] = "super"
    is_valid, errors = validate_llm_response(payload)
    assert is_valid is False
    assert "caller_name_confidence" in errors


def test_all_valid_categories_accepted():
    for cat in ISSUE_CATEGORIES:
        payload = _valid_llm_payload()
        payload["issue_category"] = cat
        is_valid, _ = validate_llm_response(payload)
        assert is_valid, f"Category '{cat}' should be valid"


def test_all_valid_priorities_accepted():
    for pri in ISSUE_PRIORITIES:
        payload = _valid_llm_payload()
        payload["issue_priority"] = pri
        is_valid, _ = validate_llm_response(payload)
        assert is_valid, f"Priority '{pri}' should be valid"


def test_all_valid_statuses_accepted():
    for status in RESOLUTION_STATUSES:
        payload = _valid_llm_payload()
        payload["resolution_status"] = status
        is_valid, _ = validate_llm_response(payload)
        assert is_valid, f"Status '{status}' should be valid"


def test_all_valid_sentiments_accepted():
    for sent in CUSTOMER_SENTIMENTS:
        payload = _valid_llm_payload()
        payload["customer_sentiment"] = sent
        is_valid, _ = validate_llm_response(payload)
        assert is_valid, f"Sentiment '{sent}' should be valid"


def test_all_valid_confidence_values_accepted():
    for conf in CONFIDENCE_VALUES:
        payload = _valid_llm_payload()
        payload["caller_name_confidence"] = conf
        is_valid, _ = validate_llm_response(payload)
        assert is_valid, f"Confidence '{conf}' should be valid"


def test_steps_taken_must_be_list():
    payload = _valid_llm_payload()
    payload["steps_taken"] = "single string"
    is_valid, errors = validate_llm_response(payload)
    assert is_valid is False
    assert "steps_taken" in errors


def test_follow_up_required_must_be_bool():
    payload = _valid_llm_payload()
    payload["follow_up_required"] = "not-a-bool"
    is_valid, errors = validate_llm_response(payload)
    assert is_valid is False
    assert "follow_up_required" in errors


def test_unknown_fields_excluded():
    payload = _valid_llm_payload()
    payload["hallucinated_field"] = "should be dropped"
    is_valid, _ = validate_llm_response(payload)
    assert is_valid is True
