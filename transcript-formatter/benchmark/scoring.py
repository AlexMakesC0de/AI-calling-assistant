"""
Scoring logic for the prompt benchmark (ISR-353).

Each fixture is scored by comparing the LLM's extracted incident form against
a hand-authored ``expected`` answer. Three metrics are produced per fixture,
each a fraction in [0.0, 1.0]:

  accuracy            - fraction of all 16 graded fields the model got right
  completeness        - of the fields that *should* hold information, the
                        fraction the model actually filled in
  hallucination_rate  - of the fields that should be empty, the fraction
                        where the model invented a concrete value
                        (lower is better)

See README.md for the full, human-readable definition of each metric.
"""

from __future__ import annotations

# --- Field groups ----------------------------------------------------------
# Short identity strings: a name, a reference number, a contact detail.
IDENTITY_FIELDS = (
    "caller_name",
    "account_or_reference",
    "contact_info",
    "agent_name",
    "follow_up_department",
)
# Closed vocabularies - graded by exact (normalised) match.
ENUM_FIELDS = (
    "issue_category",
    "issue_priority",
    "resolution_status",
    "customer_sentiment",
)
BOOL_FIELDS = ("follow_up_required",)
# Free-text fields - graded by keyword coverage. Always expected to hold text.
TEXT_FIELDS = ("issue_description", "resolution_outcome", "call_summary")
# List fields - graded by keyword coverage, may legitimately be empty.
LIST_FIELDS = ("steps_taken", "follow_up_actions")
ERROR_FIELD = "error_messages"
KEYWORD_FIELDS = TEXT_FIELDS + LIST_FIELDS + (ERROR_FIELD,)

ALL_FIELDS = IDENTITY_FIELDS + ENUM_FIELDS + BOOL_FIELDS + KEYWORD_FIELDS

# Fields that may legitimately be empty when the transcript lacks the info.
# Completeness and hallucination rate are measured only over these; the
# free-text fields are always expected to hold something and would otherwise
# skew both metrics towards a fixed value.
ABSENT_CAPABLE_FIELDS = IDENTITY_FIELDS + LIST_FIELDS + (ERROR_FIELD,)

# A keyword-scored field "passes" when it covers at least this fraction of
# the expected keywords.
KEYWORD_COVERAGE_THRESHOLD = 0.5

_ABSENT_TOKENS = {"", "not mentioned", "none", "n/a", "na", "unknown", "null"}


def _norm(value) -> str:
    return str(value if value is not None else "").strip().lower()


def _is_absent(value) -> bool:
    """True when a scalar value represents 'no information'."""
    return _norm(value) in _ABSENT_TOKENS


def _as_text(value) -> str:
    """Flatten a model field value (string or list) to a single string."""
    if isinstance(value, (list, tuple)):
        return " ".join(str(item) for item in value)
    return str(value if value is not None else "")


def _keyword_coverage(text: str, keywords: list[str]) -> float:
    """Fraction of expected keywords found (case-insensitive) in text."""
    if not keywords:
        return 1.0
    haystack = text.lower()
    hits = sum(1 for kw in keywords if str(kw).lower() in haystack)
    return hits / len(keywords)


def _score_field(field: str, expected: dict, output: dict) -> dict:
    """Grade one field. Returns a record consumed by ``score_output``."""
    raw = output.get(field)

    if field in KEYWORD_FIELDS:
        keywords = list(expected.get(f"{field}_keywords", []))
        text = _as_text(raw)
        model_filled = bool(text.strip()) and not _is_absent(text)
        expected_present = len(keywords) > 0
        if expected_present:
            coverage = _keyword_coverage(text, keywords)
            correct = model_filled and coverage >= KEYWORD_COVERAGE_THRESHOLD
        else:
            coverage = None
            correct = not model_filled
        return {
            "field": field,
            "kind": "keyword",
            "expected_present": expected_present,
            "model_filled": model_filled,
            "correct": correct,
            "coverage": coverage,
        }

    gold = expected.get(field)

    if field in ENUM_FIELDS:
        return {
            "field": field,
            "kind": "enum",
            "expected_present": True,
            "model_filled": not _is_absent(raw),
            "correct": _norm(raw) == _norm(gold),
        }

    if field in BOOL_FIELDS:
        return {
            "field": field,
            "kind": "bool",
            "expected_present": True,
            "model_filled": True,
            "correct": _norm(raw) == _norm(gold),
        }

    # Identity field.
    expected_present = not _is_absent(gold)
    model_filled = not _is_absent(raw)
    if expected_present:
        gold_n, raw_n = _norm(gold), _norm(raw)
        # Containment tolerates partial names ("Maria" vs "Maria Hendriks").
        correct = model_filled and (
            gold_n == raw_n or gold_n in raw_n or raw_n in gold_n
        )
    else:
        correct = not model_filled
    return {
        "field": field,
        "kind": "identity",
        "expected_present": expected_present,
        "model_filled": model_filled,
        "correct": correct,
    }


def score_output(expected: dict, output: dict) -> dict:
    """Score one LLM output dict against a fixture's expected answer."""
    fields = [_score_field(f, expected, output) for f in ALL_FIELDS]

    accuracy = sum(1 for f in fields if f["correct"]) / len(fields)

    absent_capable = [f for f in fields if f["field"] in ABSENT_CAPABLE_FIELDS]
    should_fill = [f for f in absent_capable if f["expected_present"]]
    should_be_empty = [f for f in absent_capable if not f["expected_present"]]

    completeness = (
        sum(1 for f in should_fill if f["model_filled"]) / len(should_fill)
        if should_fill
        else 1.0
    )
    hallucination_rate = (
        sum(1 for f in should_be_empty if f["model_filled"]) / len(should_be_empty)
        if should_be_empty
        else 0.0
    )

    return {
        "accuracy": round(accuracy, 4),
        "completeness": round(completeness, 4),
        "hallucination_rate": round(hallucination_rate, 4),
        "incorrect_fields": [f["field"] for f in fields if not f["correct"]],
        "hallucinated_fields": [
            f["field"]
            for f in should_be_empty
            if f["model_filled"]
        ],
        "fields": fields,
    }


def aggregate(fixture_results: list[dict]) -> dict:
    """Mean of each metric across all fixture results."""
    count = len(fixture_results)
    if not count:
        return {
            "accuracy": 0.0,
            "completeness": 0.0,
            "hallucination_rate": 0.0,
            "count": 0,
        }
    return {
        "accuracy": round(
            sum(r["accuracy"] for r in fixture_results) / count, 4
        ),
        "completeness": round(
            sum(r["completeness"] for r in fixture_results) / count, 4
        ),
        "hallucination_rate": round(
            sum(r["hallucination_rate"] for r in fixture_results) / count, 4
        ),
        "count": count,
    }
