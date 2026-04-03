"""
Transcript Formatter Service
=============================
Receives raw transcript text via POST /format, uses a local LLM (Ollama)
to read the transcript and fill out a structured incident form, then
returns the completed form as JSON.

The AI acts like a support analyst — it reads the conversation and extracts
all the information needed to complete the form fields automatically.
It also rates its confidence for each field it fills.
"""

import logging
import os

from flask import Flask

# Import all modules
from config import *  # noqa: F401, F403
from schemas import format_request_schema
from forms import build_incident_form
from routes import register_routes

# ---------------------------------------------------------------------------
# Flask Application Setup
# ---------------------------------------------------------------------------

app = Flask(__name__)
# Ensure Flask produces UTF-8 JSON output without escaping non-ASCII characters.
# This makes Russian (and other non-latin) text readable in responses.
app.config["JSON_AS_ASCII"] = False
app.config["TEMPLATE_DIR"] = TEMPLATE_DIR

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s – %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Register Routes
# ---------------------------------------------------------------------------

register_routes(app, format_request_schema, build_incident_form)

# ---------------------------------------------------------------------------
# Entrypoint (development only – production uses gunicorn)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
