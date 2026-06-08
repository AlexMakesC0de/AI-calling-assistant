"""
Request schemas and validation for the Transcript Formatter service.
"""

from marshmallow import Schema, fields, validate


class FormatRequestSchema(Schema):
    """
    Schema for validating transcript format requests.

    Fields:
        transcript: The raw call transcript text (required)
        include_dutch_translation: Whether to include Dutch translation in response
        call_date: Optional timestamp for the inbound message
        metadata: Optional caller/source metadata (e.g. source_channel)
    """
    transcript = fields.Str(required=True, validate=validate.Length(min=1))
    include_dutch_translation = fields.Bool(
        required=False,
        load_default=None,
        allow_none=True,
    )
    call_date = fields.DateTime(required=False, allow_none=True)
    metadata = fields.Dict(required=False, load_default=dict)

    class Meta:
        unknown = "exclude"


# Global instance for request validation
format_request_schema = FormatRequestSchema()
