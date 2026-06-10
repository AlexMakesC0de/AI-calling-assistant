"""Tests for email signature / quoted-reply stripping (ISR-346)."""

from __future__ import annotations

from email_cleaning import clean_email_body


# --- Signatures ------------------------------------------------------------

def test_strips_rfc_signature_delimiter():
    body = (
        "Machine 4 keeps stopping mid-cycle, error E-204.\n"
        "Please advise.\n"
        "-- \n"
        "Hans Bakker\n"
        "Distributor BV | +31 6 12345678"
    )
    cleaned = clean_email_body(body)
    assert "error E-204" in cleaned
    assert "Hans Bakker" not in cleaned
    assert "+31 6 12345678" not in cleaned


def test_strips_sent_from_my_iphone():
    body = "The sealer is jammed again.\n\nSent from my iPhone"
    cleaned = clean_email_body(body)
    assert "sealer is jammed" in cleaned
    assert "iPhone" not in cleaned


def test_strips_underscore_rule_signature():
    body = "Conveyor belt slips.\n____________\nKind regards,\nMaria"
    cleaned = clean_email_body(body)
    assert "Conveyor belt slips." in cleaned
    assert "Maria" not in cleaned


def test_strips_dutch_sent_from():
    body = "Storing aan machine 7.\n\nVerzonden vanaf mijn Samsung"
    cleaned = clean_email_body(body)
    assert "machine 7" in cleaned
    assert "Samsung" not in cleaned


def test_strips_closing_salutation_signoff():
    body = (
        "Machine 4 error E-204, production stopped.\n"
        "\n"
        "Met vriendelijke groet,\n"
        "Hans Bakker\n"
        "Distributor BV"
    )
    cleaned = clean_email_body(body)
    assert "error E-204" in cleaned
    assert "Hans Bakker" not in cleaned
    assert "Distributor BV" not in cleaned


def test_english_regards_signoff_stripped():
    body = "Sealer jammed.\n\nKind regards,\nMaria\nAcme Ltd"
    cleaned = clean_email_body(body)
    assert "Sealer jammed." in cleaned
    assert "Maria" not in cleaned


def test_salutation_word_in_sentence_not_stripped():
    # 'thanks' inside a sentence must not be treated as a sign-off line.
    body = "Many thanks to the engineer who flagged error E-204 last week."
    assert clean_email_body(body) == body


# --- Quoted reply chains ---------------------------------------------------

def test_strips_on_wrote_quote_header_and_quoted_lines():
    body = (
        "Yes, it still happens after the reset.\n"
        "\n"
        "On Mon, 8 Jun 2026 at 09:00, Support <support@example.com> wrote:\n"
        "> Have you tried restarting the machine?\n"
        "> Let us know.\n"
    )
    cleaned = clean_email_body(body)
    assert "still happens after the reset" in cleaned
    assert "restarting the machine" not in cleaned
    assert "wrote:" not in cleaned


def test_strips_dutch_quote_header():
    body = (
        "Het probleem is terug.\n"
        "Op 8 jun 2026 schreef Support <support@example.com>:\n"
        "> Eerdere reactie hier.\n"
    )
    cleaned = clean_email_body(body)
    assert "Het probleem is terug." in cleaned
    assert "Eerdere reactie" not in cleaned


def test_strips_original_message_divider():
    body = (
        "New error code SYS-900 today.\n"
        "-----Original Message-----\n"
        "From: someone\n"
        "old content\n"
    )
    cleaned = clean_email_body(body)
    assert "SYS-900" in cleaned
    assert "old content" not in cleaned


def test_strips_outlook_from_sent_to_block():
    body = (
        "Please see my reply below.\n"
        "\n"
        "From: Support <support@example.com>\n"
        "Sent: Monday, 8 June 2026 09:00\n"
        "To: Hans <hans@example.com>\n"
        "Subject: RE: Machine 4\n"
        "\n"
        "Earlier quoted message text.\n"
    )
    cleaned = clean_email_body(body)
    assert "Please see my reply below." in cleaned
    assert "Earlier quoted message text." not in cleaned


def test_strips_block_of_quoted_lines_without_header():
    body = (
        "Confirmed, still broken.\n"
        "> previous line one\n"
        "> previous line two\n"
    )
    cleaned = clean_email_body(body)
    assert "still broken" in cleaned
    assert "previous line one" not in cleaned


# --- Preserve legitimate technical content ---------------------------------

def test_preserves_error_codes_and_machine_refs():
    body = (
        "Machine number 4 shows error E-204 and ERR-5012.\n"
        "Voltage reads 230V, humidity 45%.\n"
        "Problem started after the film change."
    )
    assert clean_email_body(body) == body.strip()


def test_lone_gt_line_is_not_treated_as_quote():
    # A single '>' (e.g. a comparison in technical text) must not trigger a cut.
    body = "Throughput dropped.\n> 500 units/h is the target threshold.\nStill investigating."
    cleaned = clean_email_body(body)
    assert "Still investigating." in cleaned
    assert "target threshold" in cleaned


def test_no_signature_or_quote_returns_unchanged():
    body = "Simple problem report with no signature.\nMachine 9 is leaking."
    assert clean_email_body(body) == body


# --- Edge cases ------------------------------------------------------------

def test_empty_body_returns_unchanged():
    assert clean_email_body("") == ""
    assert clean_email_body("   ") == "   "


def test_reply_with_only_quoted_text_keeps_raw():
    # No new content above the quote -> keep raw rather than return empty.
    body = (
        "On Mon, 8 Jun 2026, Support wrote:\n"
        "> the whole message is quoted\n"
        "> nothing new on top\n"
    )
    cleaned = clean_email_body(body)
    assert cleaned == body.strip()


def test_signature_at_very_top_keeps_raw():
    body = "-- \njust a signature, no body"
    # cut at index 0 -> empty -> guard returns raw
    assert clean_email_body(body) == body.strip()
