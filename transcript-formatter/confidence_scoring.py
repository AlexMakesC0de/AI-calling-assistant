"""
Confidence scoring for form fields in the Transcript Formatter service.
"""

from config import SCORED_FIELDS


def _extract_confidence(ai_fields: dict) -> dict:
    """Pull confidence ratings out of the AI response into a summary.

    Returns a dict with:
      - per_field:  { field_name: "high"|"medium"|"low", ... }
      - overall:    "High" | "Medium" | "Low"
      - low_confidence_fields:  list of field names rated "low"
    """
    per_field = {}
    for field in SCORED_FIELDS:
        conf_key = f"{field}_confidence"
        conf = ai_fields.get(conf_key, "medium").lower()
        if conf not in ("high", "medium", "low"):
            conf = "medium"
        per_field[field] = conf

    # Compute overall score
    scores = {"high": 3, "medium": 2, "low": 1}
    total = sum(scores.get(v, 2) for v in per_field.values())
    avg = total / len(per_field) if per_field else 2

    if avg >= 2.5:
        overall = "High"
    elif avg >= 1.5:
        overall = "Medium"
    else:
        overall = "Low"

    low_fields = [f for f, v in per_field.items() if v == "low"]

    return {
        "per_field": per_field,
        "overall": overall,
        "low_confidence_fields": low_fields,
    }
