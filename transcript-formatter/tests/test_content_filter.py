"""Tests for content/profanity filtering (Sprint6#46).

Covers:
  Sprint6#46  Profanity Filtering — profanity replaced with [redacted] per TERM_FILTER_MODE
"""

from __future__ import annotations

from unittest.mock import patch

import content_filter as cf


# ---------------------------------------------------------------------------
# _parse_custom_terms
# ---------------------------------------------------------------------------

def test_parse_custom_terms_json_array():
    assert cf._parse_custom_terms('["foo", "Bar"]') == {"foo", "bar"}


def test_parse_custom_terms_csv():
    assert cf._parse_custom_terms("  foo, bar , baz") == {"foo", "bar", "baz"}


def test_parse_custom_terms_malformed_json_falls_back_to_csv():
    assert cf._parse_custom_terms("[bad json, still works") == {"bad json", "still works"}


def test_parse_custom_terms_empty():
    assert cf._parse_custom_terms("") == set()
    assert cf._parse_custom_terms("  ") == set()


# ---------------------------------------------------------------------------
# _compile_pattern
# ---------------------------------------------------------------------------

def test_compile_pattern_empty_returns_none():
    assert cf._compile_pattern(set()) is None


def test_compile_pattern_matches_word_boundaries():
    pat = cf._compile_pattern({"damn"})
    assert pat.search("oh damn it")
    assert not pat.search("undamned")


def test_compile_pattern_longest_first():
    pat = cf._compile_pattern({"ass", "assassination"})
    m = pat.search("assassination attempt")
    assert m.group(0) == "assassination"


# ---------------------------------------------------------------------------
# _effective_filter_mode
# ---------------------------------------------------------------------------

def test_filter_mode_from_metadata():
    assert cf._effective_filter_mode({"term_filter_mode": "custom"}) == "custom"


def test_filter_mode_off_variants():
    for val in ("off", "none", "disabled"):
        assert cf._effective_filter_mode({"term_filter_mode": val}) == "off"


def test_filter_mode_defaults_to_basic():
    assert cf._effective_filter_mode({}) == "basic"


# ---------------------------------------------------------------------------
# _sanitize_text_value — Sprint6#46 core: profanity replaced
# ---------------------------------------------------------------------------

def test_sanitize_single_char_replacement():
    pat = cf._compile_pattern({"damn"})
    result, changed = cf._sanitize_text_value("oh damn it", pat, "*")
    assert result == "oh **** it"
    assert changed is True


def test_sanitize_multi_char_replacement():
    pat = cf._compile_pattern({"damn"})
    result, changed = cf._sanitize_text_value("oh damn it", pat, "[redacted]")
    assert result == "oh [redacted] it"
    assert changed is True


def test_sanitize_no_match():
    pat = cf._compile_pattern({"damn"})
    result, changed = cf._sanitize_text_value("all good here", pat, "*")
    assert result == "all good here"
    assert changed is False


def test_sanitize_none_pattern():
    result, changed = cf._sanitize_text_value("text", None, "*")
    assert result == "text"
    assert changed is False


def test_sanitize_case_insensitive():
    pat = cf._compile_pattern({"damn"})
    result, changed = cf._sanitize_text_value("oh DAMN it", pat, "*")
    assert result == "oh **** it"
    assert changed is True


# ---------------------------------------------------------------------------
# filter_text — public API
# ---------------------------------------------------------------------------

@patch("content_filter.BASIC_FILTER_TERMS", frozenset({"badword", "offensive"}))
def test_filter_text_basic_mode():
    result = cf.filter_text("this badword is offensive content", {})
    assert "badword" not in result
    assert "offensive" not in result


@patch("content_filter.BASIC_FILTER_TERMS", frozenset({"badword"}))
def test_filter_text_off_mode_preserves():
    result = cf.filter_text("this badword stays", {"term_filter_mode": "off"})
    assert "badword" in result


def test_filter_text_custom_mode():
    result = cf.filter_text(
        "this xyzterm is custom filtered",
        {"term_filter_mode": "custom", "term_filter_custom_words": "xyzterm"},
    )
    assert "xyzterm" not in result


def test_filter_text_custom_replacement():
    result = cf.filter_text(
        "this xyzterm here",
        {
            "term_filter_mode": "custom",
            "term_filter_custom_words": "xyzterm",
            "term_filter_replacement": "[CENSORED]",
        },
    )
    assert "[CENSORED]" in result


# ---------------------------------------------------------------------------
# _apply_content_filter — form-level filtering + confidence downgrade
# ---------------------------------------------------------------------------

@patch("content_filter.BASIC_FILTER_TERMS", frozenset({"badword"}))
def test_apply_content_filter_downgrades_confidence():
    fields = {
        "issue_description": "the badword caused issues",
        "issue_description_confidence": "high",
        "call_summary": "clean summary",
        "call_summary_confidence": "high",
        "caller_name": "John",
        "agent_name": "Agent",
        "error_messages": "None",
    }
    result = cf._apply_content_filter(fields, {})
    assert "badword" not in result["issue_description"]
    assert result["issue_description_confidence"] == "low"
    assert result["call_summary_confidence"] == "high"


@patch("content_filter.BASIC_FILTER_TERMS", frozenset({"badword"}))
def test_apply_content_filter_returns_new_dict():
    fields = {"issue_description": "badword", "issue_description_confidence": "high"}
    result = cf._apply_content_filter(fields, {})
    assert result is not fields
    assert fields["issue_description"] == "badword"
