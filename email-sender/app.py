"""
Email Sender Service
=====================
Lightweight Flask API that accepts a JSON payload and dispatches it as
an email via SMTP. Used by the pipeline to send completed incident forms
to the support team.
"""

import json
import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from flask import Flask, jsonify, request
from marshmallow import Schema, fields, validate, ValidationError

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

app = Flask(__name__)

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.example.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "user@example.com")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "changeme")
SMTP_FROM = os.getenv("SMTP_FROM", "support@example.com")
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").lower() == "true"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s – %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Request Schema
# ---------------------------------------------------------------------------


class SendEmailSchema(Schema):
    """Validates the incoming POST body."""

    to = fields.Email(required=True, metadata={"description": "Recipient email."})
    subject = fields.String(
        required=True,
        validate=validate.Length(min=1, max=255),
    )
    body = fields.String(
        required=True,
        validate=validate.Length(min=1),
        metadata={"description": "Plain-text or HTML body of the email."},
    )
    html = fields.Boolean(load_default=False)
    report = fields.Dict(load_default=None, metadata={"description": "Optional report JSON to attach inline."})


send_email_schema = SendEmailSchema()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _send_smtp(to: str, subject: str, body: str, html: bool = False) -> None:
    """Send an email via the configured SMTP server.

    Parameters
    ----------
    to : str
        Recipient address.
    subject : str
        Email subject line.
    body : str
        Email body (plain text or HTML).
    html : bool
        Whether *body* is HTML.
    """
    msg = MIMEMultipart("alternative")
    msg["From"] = SMTP_FROM
    msg["To"] = to
    msg["Subject"] = subject

    subtype = "html" if html else "plain"
    msg.attach(MIMEText(body, subtype))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        if SMTP_USE_TLS:
            server.starttls()
        if SMTP_USER and SMTP_PASSWORD:
            server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(SMTP_FROM, [to], msg.as_string())


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.route("/health", methods=["GET"])
def health():
    """Liveness / readiness probe."""
    return jsonify({"status": "ok"}), 200


@app.route("/send", methods=["POST"])
def send_email():
    """Accept a JSON payload and dispatch an email.

    **Request body (JSON)**::

        {
            "to": "manager@company.com",
            "subject": "Service Report – Call #12345",
            "body": "Please find the report below ...",
            "html": false,
            "report": { ... }   // optional – appended to body
        }
    """
    json_body = request.get_json(silent=True)
    if json_body is None:
        return jsonify({"error": "Request body must be valid JSON."}), 400

    try:
        data = send_email_schema.load(json_body)
    except ValidationError as err:
        logger.warning("Validation error: %s", err.messages)
        return jsonify({"error": "Validation failed.", "details": err.messages}), 422

    body = data["body"]
    if data.get("report"):
        body += "\n\n--- Incident Form Data (JSON) ---\n" + json.dumps(data["report"], indent=2)

    try:
        _send_smtp(
            to=data["to"],
            subject=data["subject"],
            body=body,
            html=data.get("html", False),
        )
    except Exception as exc:
        logger.error("Failed to send email: %s", exc)
        return jsonify({"error": "Email delivery failed.", "details": str(exc)}), 502

    logger.info("Email sent to %s – subject: %s", data["to"], data["subject"])
    return jsonify({"status": "sent", "to": data["to"]}), 200


# ---------------------------------------------------------------------------
# Entrypoint (development only – production uses gunicorn)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002, debug=True)
