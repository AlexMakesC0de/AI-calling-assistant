"""Unit tests for output_filters (ISR-355)."""

from __future__ import annotations

import output_filters as of


# ---------------------------------------------------------------------------
# PII redaction
# ---------------------------------------------------------------------------

def _form_fields() -> dict:
    return {
        "caller_name": "Maria Hendriks",
        "contact_info": "maria@example.com",
        "agent_name": "Tom",
        "account_or_reference": "AC-44821",
        "issue_description":
            "Maria Hendriks called from 06 12345678 because her account is "
            "locked.",
        "resolution_outcome":
            "Sent password reset link to maria@example.com.",
        "call_summary": "Maria reported a locked account.",
        "error_messages": "None",
        "steps_taken": [
            "Verified Maria Hendriks's identity",
            "Sent reset link to maria@example.com",
        ],
        "follow_up_actions": [],
    }


def test_pii_redaction_default_redacts_caller_and_contact():
    out = of.apply_pii_redaction(_form_fields())
    assert out["caller_name"] == "[redacted]"
    assert out["contact_info"] == "[redacted]"
    # Defaults leave agent_name and account_or_reference alone.
    assert out["agent_name"] == "Tom"
    assert out["account_or_reference"] == "AC-44821"


def test_pii_redaction_scrubs_phones_and_emails_in_free_text():
    out = of.apply_pii_redaction(_form_fields())
    assert "06 12345678" not in out["issue_description"]
    assert "maria@example.com" not in out["resolution_outcome"]
    assert "maria@example.com" not in out["steps_taken"][1]


def test_pii_redaction_replaces_caller_name_in_free_text():
    out = of.apply_pii_redaction(_form_fields())
    assert "Maria Hendriks" not in out["issue_description"]
    assert "Maria" not in out["call_summary"]
    assert "Maria Hendriks" not in out["steps_taken"][0]


def test_pii_redaction_leaves_not_mentioned_unchanged():
    fields = {
        "caller_name": "Not mentioned",
        "contact_info": "Not mentioned",
        "issue_description": "Generic complaint with no PII.",
        "agent_name": "Tom",
    }
    out = of.apply_pii_redaction(fields)
    assert out["caller_name"] == "Not mentioned"
    assert out["contact_info"] == "Not mentioned"


def test_pii_redaction_does_not_eat_short_numeric_codes():
    fields = {
        "caller_name": "Not mentioned",
        "contact_info": "Not mentioned",
        "issue_description": "App crashed with ERR-5012 on export.",
        "error_messages": "ERR-5012",
    }
    out = of.apply_pii_redaction(fields)
    assert "ERR-5012" in out["issue_description"]
    assert out["error_messages"] == "ERR-5012"


def test_pii_redaction_disabled_via_metadata():
    out = of.apply_pii_redaction(
        _form_fields(), {"redact_pii": False},
    )
    assert out["caller_name"] == "Maria Hendriks"
    assert "maria@example.com" in out["resolution_outcome"]


def test_pii_redaction_custom_fields_via_metadata():
    out = of.apply_pii_redaction(
        _form_fields(),
        {"redact_pii_fields": ["agent_name", "caller_name"]},
    )
    assert out["agent_name"] == "[redacted]"
    assert out["caller_name"] == "[redacted]"
    # contact_info is no longer in the fields list, so it is not blanked
    # as an identity field. The free-text email scan still scrubs the
    # embedded email in resolution_outcome regardless.
    assert out["contact_info"] == "maria@example.com"
    assert "maria@example.com" not in out["resolution_outcome"]


def test_pii_redaction_custom_replacement_string():
    out = of.apply_pii_redaction(
        _form_fields(), {"redact_pii_replacement": "***"},
    )
    assert out["caller_name"] == "***"
    assert "***" in out["resolution_outcome"]


def test_pii_redaction_returns_new_dict():
    fields = _form_fields()
    out = of.apply_pii_redaction(fields)
    assert fields["caller_name"] == "Maria Hendriks"  # input unchanged
    assert out is not fields


# ---------------------------------------------------------------------------
# Low-confidence review flag
# ---------------------------------------------------------------------------

def test_review_flags_when_overall_is_low():
    confidence = {"overall": "Low", "low_confidence_fields": []}
    out = of.evaluate_confidence_review(confidence)
    assert out["required"] is True
    assert "overall_confidence_below_threshold" in out["reasons"]


def test_review_flags_when_many_low_fields():
    confidence = {
        "overall": "High",
        "low_confidence_fields": ["a", "b", "c", "d", "e"],
    }
    out = of.evaluate_confidence_review(confidence)
    assert out["required"] is True
    assert "many_low_confidence_fields" in out["reasons"]


def test_review_does_not_flag_high_confidence_with_few_low_fields():
    confidence = {"overall": "High", "low_confidence_fields": ["a"]}
    out = of.evaluate_confidence_review(confidence)
    assert out["required"] is False
    assert out["reasons"] == []


def test_review_disabled_via_metadata():
    confidence = {
        "overall": "Low",
        "low_confidence_fields": ["a"] * 10,
    }
    out = of.evaluate_confidence_review(
        confidence, {"low_confidence_review": False},
    )
    assert out["required"] is False
    assert out["reasons"] == []


def test_review_min_fields_metadata_override():
    confidence = {
        "overall": "High",
        "low_confidence_fields": ["a", "b", "c"],
    }
    out = of.evaluate_confidence_review(
        confidence, {"low_confidence_min_fields": 2},
    )
    assert out["required"] is True
    assert "many_low_confidence_fields" in out["reasons"]


def test_review_overall_threshold_medium_treats_medium_as_low():
    confidence = {"overall": "Medium", "low_confidence_fields": []}
    out = of.evaluate_confidence_review(
        confidence, {"low_confidence_overall": "medium"},
    )
    assert out["required"] is True
    assert "overall_confidence_below_threshold" in out["reasons"]


def test_review_handles_missing_confidence_dict_gracefully():
    out = of.evaluate_confidence_review({})
    assert out["required"] is False


# ---------------------------------------------------------------------------
# Off-topic detection
# ---------------------------------------------------------------------------

ON_TOPIC_TRANSCRIPT = (
    "Speaker 1: Good morning, this is Tom. How can I help?\n"
    "Speaker 2: Hi, my name is Maria Hendriks. My account is locked, "
    "reference AC-44821."
)
ON_TOPIC_OUTPUT = {
    "issue_description":
        "Maria Hendriks reports a locked account, reference AC-44821.",
    "call_summary":
        "Customer Maria Hendriks reported her account was locked.",
    "resolution_outcome":
        "Agent will verify identity and unlock the account.",
    "error_messages": "None",
    "steps_taken": ["Captured account reference AC-44821"],
    "follow_up_actions": [],
}

OFF_TOPIC_OUTPUT = {
    "issue_description":
        "Customer wants to plant tomatoes in greenhouse irrigation system.",
    "call_summary":
        "Caller asked about hydroponic fertilizer dosage for cucumbers.",
    "resolution_outcome":
        "Agent recommended weekly mineral solution refresh.",
    "error_messages": "Fertilizer pH out of bounds.",
    "steps_taken": ["Looked up greenhouse manual"],
    "follow_up_actions": ["Send irrigation calibration schedule"],
}


def test_off_topic_flags_unrelated_output():
    out = of.detect_off_topic(ON_TOPIC_TRANSCRIPT, OFF_TOPIC_OUTPUT)
    assert out["off_topic"] is True
    assert out["overlap"] < 0.10


def test_off_topic_passes_related_output():
    out = of.detect_off_topic(ON_TOPIC_TRANSCRIPT, ON_TOPIC_OUTPUT)
    assert out["off_topic"] is False
    assert out["overlap"] >= 0.10


def test_off_topic_skips_short_output():
    short_output = {"issue_description": "Hi", "call_summary": "Done."}
    out = of.detect_off_topic(ON_TOPIC_TRANSCRIPT, short_output)
    assert out["off_topic"] is False
    assert "too short" in (out["reason"] or "")


def test_off_topic_disabled_via_metadata():
    out = of.detect_off_topic(
        ON_TOPIC_TRANSCRIPT, OFF_TOPIC_OUTPUT, {"offtopic_detect": False},
    )
    assert out["off_topic"] is False


def test_off_topic_threshold_metadata_override():
    out = of.detect_off_topic(
        ON_TOPIC_TRANSCRIPT, ON_TOPIC_OUTPUT, {"offtopic_threshold": 0.99},
    )
    assert out["off_topic"] is True


def test_off_topic_empty_transcript_does_not_crash():
    out = of.detect_off_topic("", ON_TOPIC_OUTPUT)
    assert out["off_topic"] is False


DUTCH_TRANSCRIPT = (
    "Speaker 1: Goedemiddag, u spreekt met Femke.\n"
    "Speaker 2: Hallo, mijn naam is Jeroen Smit, klantnummer KL-77310, "
    "ik heb een vraag over mijn factuur."
)
DUTCH_ENGLISH_OUTPUT = {
    "issue_description":
        "Jeroen Smit asked about an invoice charge for the extended "
        "support package.",
    "call_summary":
        "Jeroen Smit queried an extended support package fee on his "
        "invoice.",
    "resolution_outcome":
        "Femke removed the package; the charge will not recur.",
    "error_messages": "None",
    "steps_taken": [
        "Identified the charge as the extended support package",
        "Removed the extended support package",
    ],
    "follow_up_actions": [],
}


def test_off_topic_handles_cross_language_when_names_overlap():
    # The proper names "Jeroen", "Smit" and "Femke" anchor the overlap
    # above the default 0.10 threshold even though the JSON values
    # follow the prompt's English-output rule.
    out = of.detect_off_topic(DUTCH_TRANSCRIPT, DUTCH_ENGLISH_OUTPUT)
    assert out["off_topic"] is False
