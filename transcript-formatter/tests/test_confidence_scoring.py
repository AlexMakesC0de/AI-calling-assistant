"""Tests for confidence scoring (Sprint3#18).

Covers:
  Sprint3#18  Low-Confidence Transcript Flagging — low confidence flagged correctly
  Sprint5#31  Low-Confidence Email Flagging — low_confidence flag set when score < threshold
"""

from __future__ import annotations

from unittest.mock import patch

import confidence_scoring as cs

MOCK_SCORED_FIELDS = [
    "caller_name", "account_or_reference", "contact_info", "agent_name",
    "issue_category", "issue_priority", "issue_description", "error_messages",
    "resolution_status", "steps_taken", "resolution_outcome",
    "follow_up_required", "follow_up_actions", "follow_up_department",
    "customer_sentiment", "call_summary",
]


@patch("confidence_scoring.SCORED_FIELDS", MOCK_SCORED_FIELDS)
class TestExtractConfidence:

    def test_all_high_yields_overall_high(self):
        ai_fields = {f"{f}_confidence": "high" for f in MOCK_SCORED_FIELDS}
        result = cs._extract_confidence(ai_fields)
        assert result["overall"] == "High"
        assert result["low_confidence_fields"] == []

    def test_all_low_yields_overall_low(self):
        ai_fields = {f"{f}_confidence": "low" for f in MOCK_SCORED_FIELDS}
        result = cs._extract_confidence(ai_fields)
        assert result["overall"] == "Low"
        assert len(result["low_confidence_fields"]) == len(MOCK_SCORED_FIELDS)

    def test_all_medium_yields_overall_medium(self):
        ai_fields = {f"{f}_confidence": "medium" for f in MOCK_SCORED_FIELDS}
        result = cs._extract_confidence(ai_fields)
        assert result["overall"] == "Medium"

    def test_mixed_confidence_correct_overall(self):
        ai_fields = {}
        for i, f in enumerate(MOCK_SCORED_FIELDS):
            ai_fields[f"{f}_confidence"] = "high" if i < 14 else "low"
        result = cs._extract_confidence(ai_fields)
        assert result["overall"] in ("High", "Medium")
        assert len(result["low_confidence_fields"]) == 2

    def test_missing_confidence_defaults_to_medium(self):
        result = cs._extract_confidence({})
        for f in MOCK_SCORED_FIELDS:
            assert result["per_field"][f] == "medium"
        assert result["overall"] == "Medium"

    def test_invalid_confidence_value_treated_as_medium(self):
        ai_fields = {"caller_name_confidence": "superduper"}
        result = cs._extract_confidence(ai_fields)
        assert result["per_field"]["caller_name"] == "medium"

    def test_low_fields_list_correct(self):
        ai_fields = {
            "caller_name_confidence": "low",
            "agent_name_confidence": "low",
            "issue_description_confidence": "high",
        }
        result = cs._extract_confidence(ai_fields)
        assert "caller_name" in result["low_confidence_fields"]
        assert "agent_name" in result["low_confidence_fields"]
        assert "issue_description" not in result["low_confidence_fields"]

    def test_per_field_dict_has_all_scored_fields(self):
        result = cs._extract_confidence({})
        assert set(result["per_field"].keys()) == set(MOCK_SCORED_FIELDS)

    def test_threshold_boundary_high(self):
        ai_fields = {}
        for i, f in enumerate(MOCK_SCORED_FIELDS):
            if i < 8:
                ai_fields[f"{f}_confidence"] = "high"
            else:
                ai_fields[f"{f}_confidence"] = "medium"
        result = cs._extract_confidence(ai_fields)
        assert result["overall"] in ("High", "Medium")
