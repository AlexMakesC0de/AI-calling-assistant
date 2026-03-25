"""
Voice Recording App
====================
Accepts audio file uploads (.wav / .mp3), transcribes them via Whisper ASR,
then automatically triggers the full pipeline:

  1. Save & validate the audio file
  2. Transcribe via Whisper (speech-to-text)  — with retry
  3. Send transcript to the Formatter (AI fills out the incident form)  — with retry
  4. Email the completed form to the support team  — with retry
  5. Store the completed form in PostgreSQL for records
"""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import magic
import psycopg2
import psycopg2.extras
import requests
from flask import Flask, jsonify, render_template, request
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)
from werkzeug.utils import secure_filename

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

app = Flask(__name__)

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "/data/shared/uploads"))
# Prefer TRANSCRIBER_URL used by current compose setup; keep WHISPER_URL for compatibility.
WHISPER_URL = os.getenv(
    "TRANSCRIBER_URL",
    os.getenv("WHISPER_URL", "http://localhost:9000/transcribe"),
)
FORMATTER_URL = os.getenv("FORMATTER_URL", "http://localhost:5001/format")
EMAIL_URL = os.getenv("EMAIL_URL", "http://email-sender:5002/send")
SUPPORT_EMAIL = os.getenv("SUPPORT_EMAIL", "support-team@example.com")

# File validation settings
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "50"))
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
ALLOWED_EXTENSIONS = {"wav", "mp3", "ogg", "flac", "m4a", "webm"}
ALLOWED_MIME_TYPES = {
    "audio/wav", "audio/x-wav", "audio/wave",
    "audio/mpeg", "audio/mp3",
    "audio/ogg", "audio/flac",
    "audio/mp4", "audio/m4a", "audio/x-m4a",
    "audio/webm",
    "video/webm",
}

# Database settings
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", os.getenv("POSTGRES_DB", "support_db"))
DB_USER = os.getenv("DB_USER", os.getenv("POSTGRES_USER", "support"))
DB_PASSWORD = os.getenv("DB_PASSWORD", os.getenv("POSTGRES_PASSWORD", "support_secret"))

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s – %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Database initialisation
# ---------------------------------------------------------------------------


def _get_db_connection():
    """Create and return a new PostgreSQL connection."""
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )


def _init_db():
    """Create the incident_forms table if it doesn't exist."""
    try:
        conn = _get_db_connection()
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS incident_forms (
                    id              SERIAL PRIMARY KEY,
                    form_id         TEXT UNIQUE NOT NULL,
                    completed_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    status          TEXT NOT NULL DEFAULT 'completed',
                    category        TEXT,
                    priority        TEXT,
                    caller_name     TEXT,
                    agent_name      TEXT,
                    sentiment       TEXT,
                    summary         TEXT,
                    audio_filename  TEXT,
                    form_data       JSONB NOT NULL,
                    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );

                CREATE INDEX IF NOT EXISTS idx_incident_forms_form_id
                    ON incident_forms (form_id);
                CREATE INDEX IF NOT EXISTS idx_incident_forms_category
                    ON incident_forms (category);
                CREATE INDEX IF NOT EXISTS idx_incident_forms_created_at
                    ON incident_forms (created_at DESC);
            """)
        conn.commit()
        conn.close()
        logger.info("Database table 'incident_forms' ready.")
    except Exception as exc:
        logger.warning("Could not initialise database (will retry on first write): %s", exc)


def _store_form(form: dict, audio_filename: str) -> bool:
    """Persist a completed incident form to PostgreSQL.

    Returns True on success, False on failure (non-fatal).
    """
    try:
        conn = _get_db_connection()
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO incident_forms
                    (form_id, completed_at, status, category, priority,
                     caller_name, agent_name, sentiment, summary,
                     audio_filename, form_data)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (form_id) DO NOTHING
                """,
                (
                    form.get("form_id"),
                    form.get("completed_at"),
                    form.get("status", "completed"),
                    form.get("issue", {}).get("category"),
                    form.get("issue", {}).get("priority"),
                    form.get("caller_information", {}).get("name"),
                    form.get("call_details", {}).get("agent_name"),
                    form.get("customer_sentiment"),
                    form.get("call_summary"),
                    audio_filename,
                    json.dumps(form),
                ),
            )
        conn.commit()
        conn.close()
        logger.info("Stored form %s in database.", form.get("form_id"))
        return True
    except Exception as exc:
        logger.error("Failed to store form in database: %s", exc)
        return False


def _get_or_create_storage_account(cur) -> int:
    """Get a service account for storage projections, creating it if needed."""
    storage_email = os.getenv("STORAGE_ACCOUNT_EMAIL", "voice-app-storage@local")
    storage_password = os.getenv("STORAGE_ACCOUNT_PASSWORD", "not-for-login")

    cur.execute("SELECT account_id FROM account WHERE account_email = %s", (storage_email,))
    row = cur.fetchone()
    if row:
        return row[0]

    cur.execute(
        """
        INSERT INTO account (password, account_email)
        VALUES (%s, %s)
        RETURNING account_id
        """,
        (storage_password, storage_email),
    )
    return cur.fetchone()[0]


def _get_or_create_file_type(cur, extension: str) -> int:
    """Get or create the file type ID for the uploaded audio extension."""
    cur.execute("SELECT filetype_id FROM filetype WHERE filetypename = %s", (extension,))
    row = cur.fetchone()
    if row:
        return row[0]

    cur.execute(
        """
        INSERT INTO filetype (filetypename)
        VALUES (%s)
        RETURNING filetype_id
        """,
        (extension,),
    )
    return cur.fetchone()[0]


def _store_storage_projection(
    audio_filename: str,
    audio_path: str,
    transcript_text: str,
    completed_at: str | None,
) -> bool:
    """Persist upload metadata and transcript into the new storage schema tables."""
    try:
        session_start = datetime.now(timezone.utc)
        session_end = session_start
        if completed_at:
            try:
                session_end = datetime.fromisoformat(completed_at.replace("Z", "+00:00"))
            except ValueError:
                logger.warning("Could not parse completed_at '%s'; using current time.", completed_at)

        extension = Path(audio_filename).suffix.lstrip(".").lower() or "unknown"
        transcript_chunks = [line.strip() for line in transcript_text.splitlines() if line.strip()]
        if not transcript_chunks and transcript_text.strip():
            transcript_chunks = [transcript_text.strip()]

        conn = _get_db_connection()
        with conn.cursor() as cur:
            account_id = _get_or_create_storage_account(cur)
            file_type_id = _get_or_create_file_type(cur, extension)

            cur.execute(
                """
                INSERT INTO recordsession (starttime, endtime, accountid)
                VALUES (%s, %s, %s)
                RETURNING recordingsession_id
                """,
                (session_start, session_end, account_id),
            )
            recording_session_id = cur.fetchone()[0]

            cur.execute(
                """
                INSERT INTO file (filetypeid, fileurl, recordingsession_id)
                VALUES (%s, %s, %s)
                RETURNING file_id
                """,
                (file_type_id, audio_path, recording_session_id),
            )
            file_id = cur.fetchone()[0]

            for idx, chunk in enumerate(transcript_chunks):
                cur.execute(
                    """
                    INSERT INTO transcriptchunk (file_id, chunk_index, content)
                    VALUES (%s, %s, %s)
                    """,
                    (file_id, idx, chunk),
                )

        conn.commit()
        conn.close()
        logger.info("Stored upload in storage schema for file %s.", audio_filename)
        return True
    except Exception as exc:
        logger.error("Failed to store upload in storage schema: %s", exc)
        return False


# ---------------------------------------------------------------------------
# File validation
# ---------------------------------------------------------------------------


def _validate_upload(file) -> tuple[bool, str]:
    """Validate an uploaded file for extension, size, and MIME type.

    Returns (is_valid, error_message).
    """
    filename = file.filename or ""

    # Check extension
    if "." not in filename:
        return False, "File has no extension."
    ext = filename.rsplit(".", 1)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return False, f"Extension '.{ext}' not allowed. Accepted: {sorted(ALLOWED_EXTENSIONS)}"

    # Check file size
    file.seek(0, 2)  # seek to end
    size = file.tell()
    file.seek(0)  # rewind
    if size > MAX_FILE_SIZE_BYTES:
        return False, f"File too large ({size / 1024 / 1024:.1f} MB). Maximum: {MAX_FILE_SIZE_MB} MB."
    if size == 0:
        return False, "File is empty (0 bytes)."

    # Check MIME type from file content (not the declared Content-Type)
    header = file.read(8192)
    file.seek(0)
    detected_mime = magic.from_buffer(header, mime=True)
    if detected_mime not in ALLOWED_MIME_TYPES:
        return False, f"Invalid audio file. Detected type: '{detected_mime}'. Expected audio format."

    return True, ""


# ---------------------------------------------------------------------------
# Retry-wrapped HTTP helpers
# ---------------------------------------------------------------------------

_RETRYABLE = (requests.exceptions.ConnectionError, requests.exceptions.Timeout)


@retry(
    retry=retry_if_exception_type(_RETRYABLE),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=30),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def _transcribe(filepath: Path) -> dict:
    """Send the audio file to the Whisper ASR service and return the result.

    Retries up to 3 times on connection errors / timeouts.
    """
    with open(filepath, "rb") as f:
        # Support both API shapes:
        # - openai-whisper-webservice: POST /asr with field audio_file + task/output params
        # - custom transcriber: POST /transcribe with field file
        if WHISPER_URL.rstrip("/").endswith("/asr"):
            files = {"audio_file": (filepath.name, f, "audio/wav")}
            params = {"task": "transcribe", "output": "json"}
            resp = requests.post(WHISPER_URL, files=files, params=params, timeout=300)
        else:
            files = {"file": (filepath.name, f, "audio/wav")}
            resp = requests.post(WHISPER_URL, files=files, timeout=300)
    resp.raise_for_status()
    return resp.json()


@retry(
    retry=retry_if_exception_type(_RETRYABLE),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=30),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def _call_formatter(transcript_text: str, metadata: dict | None = None) -> dict:
    """Send the transcript to the AI formatter and return the completed form.

    Retries up to 3 times on connection errors / timeouts.
    """
    resp = requests.post(
        FORMATTER_URL,
        json={"transcript": transcript_text, "metadata": metadata or {}},
        timeout=180,
    )
    resp.raise_for_status()
    return resp.json()


@retry(
    retry=retry_if_exception_type(_RETRYABLE),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=30),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def _send_email(payload: dict) -> dict:
    """Send the notification email via the email-sender service.

    Retries up to 3 times on connection errors / timeouts.
    """
    resp = requests.post(EMAIL_URL, json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.route("/health", methods=["GET"])
def health():
    """Liveness / readiness probe."""
    return jsonify({"status": "ok"}), 200


@app.route("/", methods=["GET"])
def index():
    """UI for recording/uploading audio and submitting to the real pipeline."""
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
def upload_audio():
    """Accept an audio file, transcribe it, and run the full pipeline.

    The pipeline runs automatically:
      1. Validate & save the file
      2. Transcribe via Whisper (with retry)
      3. AI fills out the incident form (with retry)
      4. Email the completed form to the support team (with retry)
      5. Store the completed form in the database

    **Form-data**:
        - ``file``: Audio file (.wav, .mp3, .ogg, .flac, .m4a, .webm)

    **Response (JSON)**: The full pipeline result including transcript,
    completed form, email status, and database status.
    """
    if "file" not in request.files:
        return jsonify({"error": "No file part in the request."}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No file selected."}), 400

    # ── Validate the upload ──────────────────────────────────────────────
    is_valid, error_msg = _validate_upload(file)
    if not is_valid:
        return jsonify({"error": error_msg}), 400

    filename = secure_filename(file.filename)
    filepath = UPLOAD_DIR / filename
    file.save(filepath)
    file_size_mb = filepath.stat().st_size / 1024 / 1024
    logger.info("Saved upload: %s (%.1f MB)", filepath, file_size_mb)

    result: dict = {
        "filename": filename,
        "path": str(filepath),
        "file_size_mb": round(file_size_mb, 2),
        "pipeline": {},
    }

    caller_metadata = {
        "caller_name": request.form.get("caller_name", "").strip(),
        "account_or_reference": request.form.get("account_or_reference", "").strip(),
        "contact_info": request.form.get("contact_info", "").strip(),
    }
    caller_metadata = {k: v for k, v in caller_metadata.items() if v}

    # ── Step 1: Transcribe via Whisper ────────────────────────────────────
    logger.info("Step 1: Transcribing %s via Whisper...", filename)
    try:
        transcription = _transcribe(filepath)
        transcript_text = transcription.get("text", "")
        result["pipeline"]["transcription"] = {
            "status": "success",
            "text": transcript_text,
            "word_count": len(transcript_text.split()),
        }
        logger.info("Transcription complete: %d words", len(transcript_text.split()))
    except Exception as exc:
        logger.error("Transcription failed after retries: %s", exc)
        result["pipeline"]["transcription"] = {"status": "failed", "error": str(exc)}
        return jsonify(result), 502

    if not transcript_text.strip():
        logger.warning("Transcript is empty — nothing to process.")
        result["pipeline"]["transcription"]["status"] = "empty"
        result["pipeline"]["note"] = "Transcript was empty. No form generated."
        return jsonify(result), 200

    # ── Step 2: AI fills out the incident form ───────────────────────────
    logger.info("Step 2: Sending transcript to AI formatter...")
    try:
        completed_form = _call_formatter(transcript_text, metadata=caller_metadata)
        result["pipeline"]["incident_form"] = {
            "status": "completed",
            "form_id": completed_form.get("form_id"),
            "confidence": completed_form.get("confidence"),
            "form": completed_form,
        }
        logger.info("Form completed: %s", completed_form.get("form_id"))
    except Exception as exc:
        logger.error("Form generation failed after retries: %s", exc)
        result["pipeline"]["incident_form"] = {"status": "failed", "error": str(exc)}
        return jsonify(result), 502

    # ── Step 3: Email completed form to support team ─────────────────────
    logger.info("Step 3: Emailing completed form to %s...", SUPPORT_EMAIL)
    try:
        form = completed_form
        email_body = _build_notification_email(form)
        email_payload = {
            "to": SUPPORT_EMAIL,
            "subject": f"Incident Form Completed – {form.get('form_id', 'N/A')} [{form.get('issue', {}).get('category', 'General')}]",
            "body": email_body,
            "report": form,
        }
        _send_email(email_payload)
        result["pipeline"]["email"] = {
            "status": "sent",
            "sent_to": SUPPORT_EMAIL,
        }
        logger.info("Notification email sent to %s", SUPPORT_EMAIL)
    except Exception as exc:
        logger.error("Email failed after retries: %s", exc)
        result["pipeline"]["email"] = {"status": "failed", "error": str(exc)}

    # ── Step 4: Store form in database ───────────────────────────────────
    logger.info("Step 4: Storing form in database...")
    stored = _store_form(completed_form, filename)
    storage_projection_stored = _store_storage_projection(
        audio_filename=filename,
        audio_path=str(filepath),
        transcript_text=transcript_text,
        completed_at=completed_form.get("completed_at"),
    )

    if stored and storage_projection_stored:
        db_status = "stored"
    elif stored or storage_projection_stored:
        db_status = "partial"
    else:
        db_status = "failed"

    result["pipeline"]["database"] = {
        "status": db_status,
        "incident_forms": "stored" if stored else "failed",
        "storage_projection": "stored" if storage_projection_stored else "failed",
    }

    return jsonify(result), 200


@app.route("/forms", methods=["GET"])
def list_forms():
    """Return a list of all stored incident forms.

    Query parameters:
        - ``limit``: Max results (default 50, max 500)
        - ``category``: Filter by issue category
        - ``priority``: Filter by issue priority
    """
    limit = min(int(request.args.get("limit", 50)), 500)
    category = request.args.get("category")
    priority = request.args.get("priority")

    try:
        conn = _get_db_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            query = """SELECT id, form_id, completed_at, status, category,
                              priority, caller_name, agent_name, sentiment,
                              summary, audio_filename, created_at
                       FROM incident_forms WHERE 1=1"""
            params = []
            if category:
                query += " AND category = %s"
                params.append(category)
            if priority:
                query += " AND priority = %s"
                params.append(priority)
            query += " ORDER BY created_at DESC LIMIT %s"
            params.append(limit)
            cur.execute(query, params)
            rows = cur.fetchall()
        conn.close()

        forms = []
        for row in rows:
            form_entry = dict(row)
            for key in ("completed_at", "created_at"):
                if form_entry.get(key):
                    form_entry[key] = form_entry[key].isoformat()
            forms.append(form_entry)

        return jsonify({"total": len(forms), "forms": forms}), 200
    except Exception as exc:
        logger.error("Failed to list forms: %s", exc)
        return jsonify({"error": "Database unavailable.", "details": str(exc)}), 503


@app.route("/forms/<form_id>", methods=["GET"])
def get_form(form_id):
    """Return a single incident form by form_id (full JSON data)."""
    try:
        conn = _get_db_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM incident_forms WHERE form_id = %s", (form_id,)
            )
            row = cur.fetchone()
        conn.close()

        if row is None:
            return jsonify({"error": "Form not found."}), 404

        result = dict(row)
        for key in ("completed_at", "created_at"):
            if result.get(key):
                result[key] = result[key].isoformat()

        return jsonify(result), 200
    except Exception as exc:
        logger.error("Failed to get form: %s", exc)
        return jsonify({"error": "Database unavailable.", "details": str(exc)}), 503


def _build_notification_email(form: dict) -> str:
    """Build a readable email body from the completed incident form."""
    issue = form.get("issue", {})
    resolution = form.get("resolution", {})
    caller = form.get("caller_information", {})
    call = form.get("call_details", {})
    follow_up = form.get("follow_up", {})
    confidence = form.get("confidence", {})

    steps = "\n".join(f"  - {s}" for s in resolution.get("steps_taken", [])) or "  (none)"
    follow_actions = "\n".join(f"  - {a}" for a in follow_up.get("actions", [])) or "  (none)"

    # Build confidence summary if available
    confidence_section = ""
    if confidence:
        overall = confidence.get("overall")
        low_fields = confidence.get("low_confidence_fields", [])
        if overall:
            confidence_section = f"\n\nAI CONFIDENCE: {overall}"
        if low_fields:
            confidence_section += "\n  ⚠ Low-confidence fields (may need manual review):"
            for field in low_fields:
                confidence_section += f"\n    - {field}"

    return f"""An incident form has been automatically completed from a support call recording.

═══ FORM ID: {form.get('form_id', 'N/A')} ═══

CALLER INFORMATION
  Name:      {caller.get('name', 'N/A')}
  Account:   {caller.get('account_or_reference', 'N/A')}
  Contact:   {caller.get('contact_info', 'N/A')}

CALL DETAILS
  Date:      {call.get('date', 'N/A')}
  Agent:     {call.get('agent_name', 'N/A')}
  Duration:  {call.get('duration_estimate', 'N/A')}

ISSUE
  Category:  {issue.get('category', 'N/A')}
  Priority:  {issue.get('priority', 'N/A')}
  Description: {issue.get('description', 'N/A')}
  Error messages: {issue.get('error_messages', 'None')}

RESOLUTION
  Status:    {resolution.get('status', 'N/A')}
  Steps taken:
{steps}
  Outcome:   {resolution.get('outcome', 'N/A')}

FOLLOW-UP
  Required:  {'Yes' if follow_up.get('required') else 'No'}
  Actions:
{follow_actions}
  Department: {follow_up.get('department', 'N/A')}

CUSTOMER SENTIMENT: {form.get('customer_sentiment', 'N/A')}
{confidence_section}

SUMMARY
{form.get('call_summary', 'N/A')}

───────────────────────────────────────
The full form data and transcript are attached as JSON below.
This form was generated automatically by the AI system.
"""


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

_init_db()

# ---------------------------------------------------------------------------
# Entrypoint (development only – production uses gunicorn)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
