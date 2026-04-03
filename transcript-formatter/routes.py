"""
API routes for the Transcript Formatter service.
"""

import logging
from flask import jsonify, request
from marshmallow.exceptions import ValidationError

logger = logging.getLogger(__name__)

# These will be imported in app.py after Flask app initialization
# Placeholder for format_request_schema (will be set by app.py)
format_request_schema = None
build_incident_form = None


def register_routes(app, schema, form_builder):
    """Register all routes with the Flask app.
    
    Parameters
    ----------
    app : Flask
        The Flask application instance
    schema : FormatRequestSchema
        The request validation schema
    form_builder : function
        The build_incident_form function
    """
    global format_request_schema, build_incident_form
    format_request_schema = schema
    build_incident_form = form_builder
    
    @app.route("/health", methods=["GET"])
    def health():
        """Liveness / readiness probe."""
        return jsonify({"status": "ok"}), 200

    @app.route("/format", methods=["POST"])
    def format_transcript():
        """Accept a transcript and return a completed incident form.

        **Request (JSON)**::

            {
                "transcript": "Agent: Hello ... Caller: Hi, I have a problem ...",
                "call_date": "2026-03-05T10:30:00Z",   // optional
                "metadata": {}                           // optional
            }

        **Response (JSON)**: A fully completed incident form with all fields
        extracted by AI from the transcript, plus confidence scores.
        """
        json_body = request.get_json(silent=True)
        if json_body is None:
            return jsonify({"error": "Request body must be valid JSON."}), 400

        try:
            data = format_request_schema.load(json_body)
        except ValidationError as err:
            logger.warning("Validation error: %s", err.messages)
            return jsonify({"error": "Validation failed.", "details": err.messages}), 422

        form = build_incident_form(data)
        logger.info("Completed incident form %s (confidence: %s)",
                    form["form_id"], form["confidence"]["overall"])
        response = jsonify(form)
        response.headers['Content-Language'] = 'en'
        return response, 200
