"""
Request schemas and validation for the Transcript Formatter service.
"""

from marshmallow import EXCLUDE, Schema, ValidationError, fields, validate


class FormatRequestSchema(Schema):
    """
    Schema for validating transcript format requests.

    Fields:
        transcript: The raw call transcript text (required)
        include_dutch_translation: Whether to include Dutch translation in response
        metadata: Optional per-request overrides (caller identity fields plus
            output-filter toggles such as ``redact_pii`` and
            ``offtopic_threshold``). Declared explicitly so it survives
            ``unknown = EXCLUDE`` and actually reaches ``build_incident_form``;
            without this field the per-request overrides advertised by the
            content and output filters are silently dropped at load time.
    """
    transcript = fields.Str(required=True, validate=validate.Length(min=1))
    include_dutch_translation = fields.Bool(
        required=False,
        load_default=None,
        allow_none=True
    )
    # Free-form dict — the content/output filters do their own per-key parsing
    # with safe fallbacks, so we deliberately do not constrain keys here.
    metadata = fields.Dict(required=False, load_default=dict)

    class Meta:
        unknown = EXCLUDE


# Global instance for request validation
format_request_schema = FormatRequestSchema()


# ---------------------------------------------------------------------------
# LLM response schema
# ---------------------------------------------------------------------------

CONFIDENCE_VALUES = ("high", "medium", "low")
ISSUE_CATEGORIES = (
    "Technical", "Billing", "Account", "Shipping",
    "Network", "Software", "Hardware", "General",
)
ISSUE_PRIORITIES = ("Low", "Medium", "High", "Critical")
RESOLUTION_STATUSES = ("Resolved", "Partially Resolved", "Unresolved", "Escalated")
CUSTOMER_SENTIMENTS = (
    "Very Satisfied", "Satisfied", "Neutral", "Dissatisfied", "Very Dissatisfied",
)


def _confidence_field() -> fields.Str:
    return fields.Str(required=True, validate=validate.OneOf(CONFIDENCE_VALUES))


class LLMFormResponseSchema(Schema):
    """Shape we expect back from the LLM after parsing its JSON output.

    Every field is required so a missing key is caught by validation rather
    than silently defaulted downstream. Enum fields use OneOf so an obviously
    wrong category (e.g. "MaybeBilling") fails fast and triggers the retry
    flow.
    """

    caller_name = fields.Str(required=True)
    caller_name_confidence = _confidence_field()
    account_or_reference = fields.Str(required=True)
    account_or_reference_confidence = _confidence_field()
    contact_info = fields.Str(required=True)
    contact_info_confidence = _confidence_field()
    agent_name = fields.Str(required=True)
    agent_name_confidence = _confidence_field()
    issue_category = fields.Str(required=True, validate=validate.OneOf(ISSUE_CATEGORIES))
    issue_category_confidence = _confidence_field()
    issue_priority = fields.Str(required=True, validate=validate.OneOf(ISSUE_PRIORITIES))
    issue_priority_confidence = _confidence_field()
    issue_description = fields.Str(required=True)
    issue_description_confidence = _confidence_field()
    error_messages = fields.Str(required=True)
    error_messages_confidence = _confidence_field()
    resolution_status = fields.Str(
        required=True, validate=validate.OneOf(RESOLUTION_STATUSES)
    )
    resolution_status_confidence = _confidence_field()
    steps_taken = fields.List(fields.Str(), required=True)
    steps_taken_confidence = _confidence_field()
    resolution_outcome = fields.Str(required=True)
    resolution_outcome_confidence = _confidence_field()
    follow_up_required = fields.Bool(required=True)
    follow_up_required_confidence = _confidence_field()
    follow_up_actions = fields.List(fields.Str(), required=True)
    follow_up_actions_confidence = _confidence_field()
    follow_up_department = fields.Str(required=True)
    follow_up_department_confidence = _confidence_field()
    customer_sentiment = fields.Str(
        required=True, validate=validate.OneOf(CUSTOMER_SENTIMENTS)
    )
    customer_sentiment_confidence = _confidence_field()
    call_summary = fields.Str(required=True)
    call_summary_confidence = _confidence_field()

    class Meta:
        unknown = EXCLUDE


llm_response_schema = LLMFormResponseSchema()


def validate_llm_response(payload: dict) -> tuple[bool, dict]:
    """Validate a parsed LLM response dict against the expected schema.

    Returns
    -------
    (is_valid, errors)
        is_valid is True when the payload matches the schema. errors is the
        marshmallow error dict on failure, or an empty dict on success.
    """
    try:
        llm_response_schema.load(payload)
    except ValidationError as exc:
        return False, exc.messages
    return True, {}
