"""Tests for WhatsApp ingest helpers (Sprint5#36–42).

Covers:
  Sprint5#36  Twilio Webhook Receives Message — message type inference
  Sprint5#38  WhatsApp Media Download — filename sanitization
  Sprint5#39  Twilio Signature Validation — forged request rejected
  Sprint5#41  WhatsApp Auto-Acknowledgment — auto-reply TwiML
  Sprint5#42  WhatsApp Auto-Acknowledgment — reply content

These tests import individual helper functions and avoid starting the Flask
app or connecting to external services.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch
import importlib


# ---------------------------------------------------------------------------
# _safe_stem — Sprint5#38: filename sanitization
# ---------------------------------------------------------------------------

def test_safe_stem_alphanumeric():
    from app import _safe_stem
    assert _safe_stem("abc123") == "abc123"


def test_safe_stem_special_chars_replaced():
    from app import _safe_stem
    assert _safe_stem("hello world!@#") == "hello_world___"


def test_safe_stem_preserves_hyphens_underscores():
    from app import _safe_stem
    assert _safe_stem("my-file_name") == "my-file_name"


def test_safe_stem_truncates_at_120():
    from app import _safe_stem
    long = "a" * 200
    assert len(_safe_stem(long)) == 120


def test_safe_stem_empty_returns_msg():
    from app import _safe_stem
    assert _safe_stem("") == "msg"


def test_safe_stem_all_special_returns_underscored():
    from app import _safe_stem
    result = _safe_stem("!@#$%")
    assert all(c == "_" for c in result)


# ---------------------------------------------------------------------------
# _infer_message_type — Sprint5#36: message type detection
# ---------------------------------------------------------------------------

def test_infer_text_when_no_media():
    from app import _infer_message_type
    assert _infer_message_type(0, {}) == "text"


def test_infer_voice_note():
    from app import _infer_message_type
    assert _infer_message_type(1, {"MediaContentType0": "audio/ogg"}) == "voice_note"


def test_infer_voice_note_mpeg():
    from app import _infer_message_type
    assert _infer_message_type(1, {"MediaContentType0": "audio/mpeg"}) == "voice_note"


def test_infer_image():
    from app import _infer_message_type
    assert _infer_message_type(1, {"MediaContentType0": "image/jpeg"}) == "image"


def test_infer_video():
    from app import _infer_message_type
    assert _infer_message_type(1, {"MediaContentType0": "video/mp4"}) == "video"


def test_infer_document():
    from app import _infer_message_type
    assert _infer_message_type(1, {"MediaContentType0": "application/pdf"}) == "document"


def test_infer_document_missing_content_type():
    from app import _infer_message_type
    assert _infer_message_type(1, {}) == "document"


# ---------------------------------------------------------------------------
# _twiml — Sprint5#41, Sprint5#42: auto-acknowledgment
# ---------------------------------------------------------------------------

def test_twiml_with_text():
    from app import _twiml
    with patch("app.SILENT_REPLY", False):
        resp = _twiml("Got it — processing your message.")
        body = resp.data.decode()
        assert "Got it" in body
        assert "application/xml" in resp.content_type


def test_twiml_silent_reply():
    with patch("app.SILENT_REPLY", True):
        from app import _twiml
        resp = _twiml("This should not appear")
        body = resp.data.decode()
        assert "This should not appear" not in body


def test_twiml_none_text():
    with patch("app.SILENT_REPLY", False):
        from app import _twiml
        resp = _twiml(None)
        body = resp.data.decode()
        assert "<Message>" not in body


def test_twiml_returns_xml_mimetype():
    with patch("app.SILENT_REPLY", False):
        from app import _twiml
        resp = _twiml("test")
        assert "application/xml" in resp.content_type


# ---------------------------------------------------------------------------
# Signature validation — Sprint5#39
# ---------------------------------------------------------------------------

def test_signature_validation_disabled_allows_all():
    with patch("app.VALIDATE_SIGNATURE", False):
        from app import _signature_valid
        assert _signature_valid() is True


def test_signature_validation_no_token_rejects():
    with patch("app.VALIDATE_SIGNATURE", True), \
         patch("app._validator", None):
        from app import _signature_valid
        assert _signature_valid() is False
