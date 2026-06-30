"""Tests for forms.py helper functions (Sprint2#5, Sprint3#14).

Covers:
  Sprint2#5   Auto-Translation of Final Summary to Dutch — translation helpers
  Sprint3#14  Summary Quality Fallback Template — refusal detection, form helpers
"""

from __future__ import annotations

import forms


# ---------------------------------------------------------------------------
# _looks_like_translation_refusal — Sprint3#14 fallback detection
# ---------------------------------------------------------------------------

def test_refusal_detects_dutch_refusal():
    assert forms._looks_like_translation_refusal("Ik kan niet vertalen") is True


def test_refusal_detects_english_refusal():
    assert forms._looks_like_translation_refusal("I can't help with that") is True
    assert forms._looks_like_translation_refusal("I cannot assist you") is True


def test_refusal_detects_sorry():
    assert forms._looks_like_translation_refusal("Sorry, but I can't do that.") is True


def test_refusal_rejects_normal_text():
    assert forms._looks_like_translation_refusal(
        "De printer op de tweede verdieping werkt niet."
    ) is False


def test_refusal_handles_empty():
    assert forms._looks_like_translation_refusal("") is False
    assert forms._looks_like_translation_refusal(None) is False


def test_refusal_case_insensitive():
    assert forms._looks_like_translation_refusal("I CAN'T do that") is True


# ---------------------------------------------------------------------------
# _normalize_for_compare
# ---------------------------------------------------------------------------

def test_normalize_strips_non_alnum():
    assert forms._normalize_for_compare("Hello, World!") == "helloworld"


def test_normalize_lowercases():
    assert forms._normalize_for_compare("ABC123") == "abc123"


def test_normalize_empty():
    assert forms._normalize_for_compare("") == ""
    assert forms._normalize_for_compare(None) == ""


# ---------------------------------------------------------------------------
# _as_bool
# ---------------------------------------------------------------------------

def test_as_bool_true_values():
    for val in (True, 1, 1.0, "1", "true", "yes", "on", "TRUE", "Yes"):
        assert forms._as_bool(val) is True, f"{val!r} should be True"


def test_as_bool_false_values():
    for val in (False, 0, 0.0, "0", "false", "no", "off", "FALSE", "No"):
        assert forms._as_bool(val) is False, f"{val!r} should be False"


def test_as_bool_none_uses_default():
    assert forms._as_bool(None, default=True) is True
    assert forms._as_bool(None, default=False) is False


def test_as_bool_unknown_string_uses_default():
    assert forms._as_bool("maybe", default=True) is True
    assert forms._as_bool("maybe", default=False) is False


# ---------------------------------------------------------------------------
# _likely_untranslated_english — Sprint2#5 translation detection
# ---------------------------------------------------------------------------

def test_untranslated_identical_english():
    src = "The account is locked, please reset."
    assert forms._likely_untranslated_english(src, src) is True


def test_untranslated_normalized_match():
    src = "The account is locked."
    dst = "the account is locked"
    assert forms._likely_untranslated_english(src, dst) is True


def test_translated_dutch_detected():
    src = "The account is locked."
    dst = "Het account is vergrendeld."
    assert forms._likely_untranslated_english(src, dst) is False


def test_untranslated_empty_strings():
    assert forms._likely_untranslated_english("", "") is False
    assert forms._likely_untranslated_english("text", "") is False
    assert forms._likely_untranslated_english("", "text") is False


def test_untranslated_non_english_source():
    src = "Dit is een Nederlandse zin."
    assert forms._likely_untranslated_english(src, src) is False


# ---------------------------------------------------------------------------
# _estimate_duration
# ---------------------------------------------------------------------------

def test_estimate_duration_short():
    transcript = " ".join(["word"] * 75)
    result = forms._estimate_duration(transcript)
    assert "0" in result or "less" in result.lower() or "1" in result


def test_estimate_duration_long():
    transcript = " ".join(["word"] * 750)
    result = forms._estimate_duration(transcript)
    assert "5" in result or "min" in result.lower()


def test_estimate_duration_empty():
    result = forms._estimate_duration("")
    assert result is not None
