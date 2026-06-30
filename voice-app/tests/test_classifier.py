"""Tests for classifier decision logic (Sprint2#2, Sprint5#30, Sprint5#31).

Covers:
  Sprint2#2   Filter Out Non-Service Related Calls — non-service filtered
  Sprint5#30  Email Classification — support/not_support/unclear classified correctly
  Sprint5#31  Low-Confidence Email Flagging — low_confidence flag based on threshold
"""

from __future__ import annotations

from unittest.mock import patch

from classifier import should_create_case, unclear_confidence_threshold


# ---------------------------------------------------------------------------
# should_create_case — Sprint2#2 core: non-service filtered
# ---------------------------------------------------------------------------

def test_support_label_creates_case():
    assert should_create_case({"label": "support", "confidence": 0.9}) is True


def test_support_label_creates_case_regardless_of_low_confidence():
    assert should_create_case({"label": "support", "confidence": 0.1}) is True


def test_not_support_never_creates_case():
    assert should_create_case({"label": "not_support", "confidence": 0.95}) is False


def test_not_support_low_confidence_still_rejected():
    assert should_create_case({"label": "not_support", "confidence": 0.1}) is False


# ---------------------------------------------------------------------------
# unclear label — Sprint5#30, Sprint5#31: confidence threshold
# ---------------------------------------------------------------------------

def test_unclear_high_confidence_creates_case():
    assert should_create_case({"label": "unclear", "confidence": 0.8}) is True


def test_unclear_low_confidence_does_not_create_case():
    assert should_create_case({"label": "unclear", "confidence": 0.3}) is False


@patch.dict("os.environ", {"CLASSIFIER_UNCLEAR_THRESHOLD": "0.55"})
def test_unclear_at_threshold_creates_case():
    threshold = unclear_confidence_threshold()
    assert should_create_case({"label": "unclear", "confidence": threshold}) is True


@patch.dict("os.environ", {"CLASSIFIER_UNCLEAR_THRESHOLD": "0.55"})
def test_unclear_below_threshold_does_not_create_case():
    threshold = unclear_confidence_threshold()
    assert should_create_case({"label": "unclear", "confidence": threshold - 0.01}) is False


# ---------------------------------------------------------------------------
# unclear_confidence_threshold — env configuration
# ---------------------------------------------------------------------------

@patch.dict("os.environ", {"CLASSIFIER_UNCLEAR_THRESHOLD": "0.75"})
def test_threshold_from_env():
    assert unclear_confidence_threshold() == 0.75


@patch.dict("os.environ", {}, clear=False)
def test_threshold_default():
    import os
    os.environ.pop("CLASSIFIER_UNCLEAR_THRESHOLD", None)
    assert unclear_confidence_threshold() == 0.55


@patch.dict("os.environ", {"CLASSIFIER_UNCLEAR_THRESHOLD": "not-a-number"})
def test_threshold_invalid_uses_default():
    assert unclear_confidence_threshold() == 0.55


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_missing_label_falls_through_to_unclear_logic():
    # No label → not "support" and not "not_support" → unclear path → confidence check
    assert should_create_case({"confidence": 0.9}) is True
    assert should_create_case({"confidence": 0.1}) is False


def test_missing_confidence_defaults_to_zero():
    assert should_create_case({"label": "unclear"}) is False


def test_empty_classification():
    assert should_create_case({}) is False
