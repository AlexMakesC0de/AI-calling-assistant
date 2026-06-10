"""
Strip email signatures and quoted reply chains before AI analysis (ISR-346).

Inbound support emails carry a lot of noise the AI shouldn't analyse: the
sender's signature block, "Sent from my iPhone" footers, and the quoted text
of earlier messages in a reply chain. Feeding that to the formatter dilutes
the extraction and can put another person's details into the case.

``clean_email_body`` removes those while deliberately preserving the real
content — error codes, machine numbers, and technical text are never the
trigger for a cut. The caller keeps the original raw body for the archive;
this only produces the cleaned text used for analysis.
"""

from __future__ import annotations

import re

# --- Signature delimiters ---------------------------------------------------
# A line that, on its own, marks the start of a signature block. Matched
# against the stripped line so trailing whitespace doesn't matter.
_SIGNATURE_LINE_PATTERNS = [
    re.compile(r"^--$"),                       # RFC 3676 signature delimiter
    re.compile(r"^-- $"),                      # same, with the canonical space
    re.compile(r"^_{3,}$"),                    # an underscore rule
    re.compile(r"^={3,}$"),                    # an equals rule
    re.compile(r"^sent from my .+", re.IGNORECASE),        # mobile footers
    re.compile(r"^sent from (mail|outlook|my \w+) .+", re.IGNORECASE),
    re.compile(r"^get outlook for \w+", re.IGNORECASE),
    re.compile(r"^verzonden vanaf .+", re.IGNORECASE),     # Dutch "Sent from"
]

# A line that is *only* a closing salutation marks the start of a sign-off.
# Anchored to the whole line so technical content (which is never just a
# salutation) is never matched. English / Dutch / German for the SSM Repak
# customer base.
_CLOSING_SALUTATION_PATTERNS = [
    re.compile(r"^(kind|best|warm|kindest)\s+regards[,.!]?$", re.IGNORECASE),
    re.compile(r"^regards[,.!]?$", re.IGNORECASE),
    re.compile(r"^(many\s+)?thanks(\s+again)?[,.!]?$", re.IGNORECASE),
    re.compile(r"^thank you[,.!]?$", re.IGNORECASE),
    re.compile(r"^cheers[,.!]?$", re.IGNORECASE),
    re.compile(r"^sincerely[,.!]?$", re.IGNORECASE),
    re.compile(r"^met vriendelijke groet(en)?[,.!]?$", re.IGNORECASE),  # Dutch
    re.compile(r"^vriendelijke groet(en)?[,.!]?$", re.IGNORECASE),
    re.compile(r"^groet(en)?[,.!]?$", re.IGNORECASE),
    re.compile(r"^mvg[,.!]?$", re.IGNORECASE),                          # Dutch abbr.
    re.compile(r"^mit freundlichen gr(ü|ue)ssen[,.!]?$", re.IGNORECASE),  # German
]

# --- Quoted-reply headers ---------------------------------------------------
# The header line that introduces a quoted previous message.
_QUOTE_HEADER_PATTERNS = [
    re.compile(r"^on .+ wrote:$", re.IGNORECASE),          # On <date>, <name> wrote:
    re.compile(r"^op .+ schreef .+:$", re.IGNORECASE),     # Dutch: Op <date> schreef <name>:
    re.compile(r"^-{2,}\s*original message\s*-{2,}$", re.IGNORECASE),
    re.compile(r"^-{2,}\s*oorspronkelijk bericht\s*-{2,}$", re.IGNORECASE),
]

# Outlook-style quoted header block: a "From:" line followed shortly by
# Sent/To/Subject lines (English or Dutch). Treated as a boundary only when the
# follow-up lines are present, so a legitimate "From: the engineer's view ..."
# sentence is not mistaken for a quote.
_FROM_LINE = re.compile(r"^(from|van):\s+\S", re.IGNORECASE)
_FOLLOWUP_LINE = re.compile(
    r"^(sent|verzonden|to|aan|subject|onderwerp|date|datum|cc):\s", re.IGNORECASE
)

_QUOTED_LINE = re.compile(r"^\s*>")


def _is_signature_line(stripped: str) -> bool:
    if any(p.match(stripped) for p in _SIGNATURE_LINE_PATTERNS):
        return True
    return any(p.match(stripped) for p in _CLOSING_SALUTATION_PATTERNS)


def _is_quote_header(stripped: str) -> bool:
    if not stripped:
        return False
    return any(p.match(stripped) for p in _QUOTE_HEADER_PATTERNS)


def _is_outlook_header_block(lines: list[str], idx: int) -> bool:
    """True when lines[idx] starts an Outlook quoted-header block."""
    if not _FROM_LINE.match(lines[idx].strip()):
        return False
    # Look at the next few non-blank lines for Sent/To/Subject markers.
    for j in range(idx + 1, min(idx + 5, len(lines))):
        nxt = lines[j].strip()
        if not nxt:
            continue
        if _FOLLOWUP_LINE.match(nxt):
            return True
        # First non-blank line after From: that isn't a header marker -> not a block.
        return False
    return False


def _quoted_run_length(lines: list[str], idx: int) -> int:
    """Number of consecutive quoted ('>'-prefixed) lines starting at idx."""
    count = 0
    for line in lines[idx:]:
        if _QUOTED_LINE.match(line):
            count += 1
        elif line.strip() == "":
            # allow a single blank line inside a quoted block
            if count:
                count += 1
                continue
            break
        else:
            break
    return count


def _find_cut_index(lines: list[str]) -> int:
    """Index of the first line that begins a signature or quoted reply block."""
    for i, line in enumerate(lines):
        stripped = line.strip()
        if _is_signature_line(stripped):
            return i
        if _is_quote_header(stripped):
            return i
        if _is_outlook_header_block(lines, i):
            return i
        # A run of quoted lines (>=2) marks the start of an inline quote chain.
        # A lone '>' line is left alone so it can't eat legitimate content.
        if _QUOTED_LINE.match(line) and _quoted_run_length(lines, i) >= 2:
            return i
    return len(lines)


def clean_email_body(body: str) -> str:
    """Return ``body`` with the signature and quoted-reply chain removed.

    The original is never mutated. If detection would remove everything (e.g.
    a reply containing only quoted text and no new content), the original body
    is returned unchanged so nothing is silently lost — the caller can decide
    what to do with a content-free reply.
    """
    if not body or not body.strip():
        return body

    lines = body.splitlines()
    cut = _find_cut_index(lines)
    cleaned = "\n".join(lines[:cut]).strip()

    if not cleaned:
        # Everything looked like a signature/quote — keep the raw body rather
        # than hand the pipeline an empty string.
        return body.strip()
    return cleaned
