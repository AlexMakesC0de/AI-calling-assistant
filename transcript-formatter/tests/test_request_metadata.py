"""
Regression tests for per-request metadata flowing through the request schema
into the output filters (ISR-355 follow-up).

The output/content filters are configurable per request via a ``metadata``
block, but ``FormatRequestSchema`` originally declared only ``transcript`` and
``include_dutch_translation`` with ``unknown = EXCLUDE`` — so any ``metadata``
in the POST body was stripped at load time and the per-request overrides never
reached ``build_incident_form``. These tests lock the fix: ``metadata`` must
survive schema validation and actually drive the filters.
"""

from __future__ import annotations

import output_filters as of
from schemas import format_request_schema


def test_metadata_survives_schema_load():
    data = format_request_schema.load(
        {"transcript": "hi", "metadata": {"redact_pii": False}}
    )
    assert data.get("metadata") == {"redact_pii": False}


def test_metadata_absent_defaults_to_empty_dict():
    data = format_request_schema.load({"transcript": "hi"})
    # build_incident_form does `data.get("metadata", {})`; the load_default
    # makes that an empty dict rather than a missing key.
    assert data.get("metadata") == {}


def test_unknown_top_level_keys_still_excluded():
    data = format_request_schema.load(
        {"transcript": "hi", "bogus_top_level": "x"}
    )
    assert "bogus_top_level" not in data


def test_loaded_metadata_disables_pii_redaction_end_to_end():
    """The metadata that the schema produces must actually drive the filter.

    This is the regression the in-stack check caught: with redaction on by
    default the caller name is blanked, but a request asking to disable it
    must preserve the name once metadata reaches the filter.
    """
    fields = {"caller_name": "Maria Hendriks", "contact_info": "x@y.com"}

    data_off = format_request_schema.load(
        {"transcript": "hi", "metadata": {"redact_pii": False}}
    )
    out_off = of.apply_pii_redaction(fields, data_off["metadata"])
    assert out_off["caller_name"] == "Maria Hendriks"

    # And the default (no metadata) still redacts.
    data_default = format_request_schema.load({"transcript": "hi"})
    out_default = of.apply_pii_redaction(fields, data_default["metadata"])
    assert out_default["caller_name"] == "[redacted]"


def test_loaded_metadata_drives_offtopic_threshold():
    """A per-request offtopic_threshold from the schema must take effect."""
    data = format_request_schema.load(
        {"transcript": "hi", "metadata": {"offtopic_threshold": 0.99}}
    )
    transcript = (
        "Speaker 1: Hello, this is Tom. Speaker 2: My account AC-44821 "
        "is locked, my name is Maria Hendriks."
    )
    ai_fields = {
        "issue_description": "Maria Hendriks account AC-44821 locked.",
        "call_summary": "Customer Maria Hendriks reported a locked account.",
        "resolution_outcome": "Agent will reset the account.",
        "error_messages": "None",
        "steps_taken": ["Captured account reference AC-44821"],
        "follow_up_actions": [],
    }
    result = of.detect_off_topic(transcript, ai_fields, data["metadata"])
    # With a 0.99 threshold even an on-topic answer is flagged off-topic.
    assert result["off_topic"] is True
