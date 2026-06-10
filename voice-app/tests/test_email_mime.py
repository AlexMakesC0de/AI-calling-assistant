"""Tests for MIME / plain-text / HTML email body extraction (ISR-349)."""

from __future__ import annotations

from email.message import EmailMessage

from email_mime import extract_text_body, html_to_text


# --- html_to_text ----------------------------------------------------------

def test_html_to_text_strips_tags_keeps_content():
    html = "<p>Machine 4 error <b>E-204</b></p><p>Production stopped.</p>"
    text = html_to_text(html)
    assert "Machine 4 error E-204" in text
    assert "Production stopped." in text
    assert "<" not in text and ">" not in text


def test_html_to_text_decodes_entities():
    assert html_to_text("Voltage &gt; 230V &amp; rising") == "Voltage > 230V & rising"


def test_html_to_text_removes_script_and_style():
    html = "<style>.x{color:red}</style><p>Real content E-204</p><script>evil()</script>"
    text = html_to_text(html)
    assert "Real content E-204" in text
    assert "evil" not in text and "color:red" not in text


def test_html_to_text_br_becomes_newline():
    assert "line1\nline2" in html_to_text("line1<br>line2")


# --- plain text ------------------------------------------------------------

def test_plain_text_message_routed_as_is():
    msg = EmailMessage()
    msg["Subject"] = "Machine down"
    msg.set_content("Machine 4 error E-204.\nProduction stopped.")
    raw = msg.as_string()
    body = extract_text_body(raw)
    assert "Machine 4 error E-204." in body
    assert "Production stopped." in body
    assert "<" not in body


def test_bare_string_without_headers():
    body = extract_text_body("Just a plain problem report, machine 9 leaking.")
    assert "machine 9 leaking" in body


# --- multipart prefers text/plain ------------------------------------------

def test_multipart_prefers_text_plain():
    msg = EmailMessage()
    msg["Subject"] = "Issue"
    msg.set_content("PLAIN: machine 4 error E-204")
    msg.add_alternative(
        "<p>HTML: machine 4 error E-204</p>", subtype="html"
    )
    body = extract_text_body(msg.as_string())
    assert "PLAIN: machine 4 error E-204" in body
    assert "HTML:" not in body


# --- html-only -------------------------------------------------------------

def test_html_only_message_stripped():
    msg = EmailMessage()
    msg["Subject"] = "Issue"
    msg.set_content("<html><body><p>Sealer jammed, code <b>ERR-5012</b></p></body></html>", subtype="html")
    body = extract_text_body(msg.as_string())
    assert "Sealer jammed, code ERR-5012" in body
    assert "<" not in body and ">" not in body


# --- malformed / edge ------------------------------------------------------

def test_malformed_mime_falls_back_to_raw():
    raw = "From garbage not really:: a header\n\nmachine 7 error E-900"
    body = extract_text_body(raw)
    assert "machine 7 error E-900" in body


def test_html_in_garbage_is_stripped_on_fallback():
    raw = "<div>broken mime but <b>code SYS-900</b></div>"
    body = extract_text_body(raw)
    assert "code SYS-900" in body
    assert "<" not in body


def test_empty_and_none_return_empty():
    assert extract_text_body("") == ""
    assert extract_text_body("   ") == ""
    assert extract_text_body(None) == ""


def test_bytes_input_supported():
    msg = EmailMessage()
    msg.set_content("bytes path: machine 2 error E-101")
    body = extract_text_body(msg.as_bytes())
    assert "machine 2 error E-101" in body
