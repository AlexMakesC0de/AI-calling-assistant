import logging
from typing import Any

from flask import Flask, jsonify, render_template, request
from werkzeug.utils import secure_filename

from clients import PipelineClients
from config import AppConfig
from email_builder import EmailBodyBuilder
from repository import PostgresRepository
from validation import UploadValidator


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)


class VoiceRecordingApp:
    def __init__(self, config: AppConfig):
        self._config = config
        self._db = PostgresRepository(config, logger)
        self._validator = UploadValidator(config)
        self._clients = PipelineClients(config, logger)

        self.app = Flask(__name__)
        self._register_routes()
        self._db.init_db()

    def _register_routes(self) -> None:
        @self.app.route("/health", methods=["GET"])
        def health():
            return jsonify({"status": "ok"}), 200

        @self.app.route("/", methods=["GET"])
        def index():
            return render_template("index.html")

        @self.app.route("/upload", methods=["POST"])
        def upload_audio():
            if "file" not in request.files:
                return jsonify({"error": "No file part in the request."}), 400

            file = request.files["file"]
            if file.filename == "":
                return jsonify({"error": "No file selected."}), 400

            is_valid, error_msg = self._validator.validate(file)
            if not is_valid:
                return jsonify({"error": error_msg}), 400

            filename = secure_filename(file.filename)
            filepath = self._config.upload_dir / filename
            file.save(filepath)
            file_size_mb = filepath.stat().st_size / 1024 / 1024
            logger.info("Saved upload: %s (%.1f MB)", filepath, file_size_mb)

            result: dict[str, Any] = {
                "filename": filename,
                "path": str(filepath),
                "file_size_mb": round(file_size_mb, 2),
                "pipeline": {},
            }

            caller_metadata = {
                "caller_name": request.form.get("caller_name", "").strip(),
                "account_or_reference": request.form.get(
                    "account_or_reference", ""
                ).strip(),
                "contact_info": request.form.get("contact_info", "").strip(),
                "term_filter_mode": request.form.get("term_filter_mode", "").strip(),
                "term_filter_custom_words": request.form.get(
                    "term_filter_custom_words", ""
                ).strip(),
                "term_filter_replacement": request.form.get(
                    "term_filter_replacement", ""
                ).strip(),
            }
            caller_metadata = {k: v for k, v in caller_metadata.items() if v}

            logger.info("Step 1: Transcribing %s via Whisper...", filename)
            try:
                transcription = self._clients.transcribe(filepath)
                transcript_text = transcription.get("text", "")
                result["pipeline"]["transcription"] = {
                    "status": "success",
                    "text": transcript_text,
                    "word_count": len(transcript_text.split()),
                }
                logger.info(
                    "Transcription complete: %d words", len(transcript_text.split())
                )
            except Exception as exc:
                logger.error("Transcription failed after retries: %s", exc)
                result["pipeline"]["transcription"] = {
                    "status": "failed",
                    "error": str(exc),
                }
                return jsonify(result), 502

            if not transcript_text.strip():
                logger.warning("Transcript is empty - nothing to process.")
                result["pipeline"]["transcription"]["status"] = "empty"
                result["pipeline"]["note"] = "Transcript was empty. No form generated."
                return jsonify(result), 200

            logger.info("Step 2: Sending transcript to AI formatter...")
            try:
                completed_form = self._clients.call_formatter(
                    transcript_text, metadata=caller_metadata
                )
                result["pipeline"]["incident_form"] = {
                    "status": "completed",
                    "form_id": completed_form.get("form_id"),
                    "confidence": completed_form.get("confidence"),
                    "form": completed_form,
                }
                logger.info("Form completed: %s", completed_form.get("form_id"))
            except Exception as exc:
                logger.error("Form generation failed after retries: %s", exc)
                result["pipeline"]["incident_form"] = {
                    "status": "failed",
                    "error": str(exc),
                }
                return jsonify(result), 502

            logger.info(
                "Step 3: Emailing completed form to %s...", self._config.support_email
            )
            try:
                form = completed_form
                email_body = EmailBodyBuilder.build(form)
                email_payload = {
                    "to": self._config.support_email,
                    "subject": (
                        f"Incident Form Completed - {form.get('form_id', 'N/A')} "
                        f"[{form.get('issue', {}).get('category', 'General')}]"
                    ),
                    "body": email_body,
                    "report": form,
                }
                self._clients.send_email(email_payload)
                result["pipeline"]["email"] = {
                    "status": "sent",
                    "sent_to": self._config.support_email,
                }
                logger.info(
                    "Notification email sent to %s", self._config.support_email
                )
            except Exception as exc:
                logger.error("Email failed after retries: %s", exc)
                result["pipeline"]["email"] = {"status": "failed", "error": str(exc)}

            logger.info("Step 4: Storing form in database...")
            storage_result = self._db.store_upload_with_form(
                form=completed_form,
                audio_filename=filename,
                audio_path=str(filepath),
                transcript_text=transcript_text,
                completed_at=completed_form.get("completed_at"),
            )
            storage_projection_stored = storage_result is not None
            stored = bool(storage_result and storage_result.get("incident_form_stored"))

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

        @self.app.route("/forms", methods=["GET"])
        def list_forms():
            limit = min(int(request.args.get("limit", 50)), 500)
            category = request.args.get("category")
            priority = request.args.get("priority")

            try:
                forms = self._db.list_forms(limit=limit, category=category, priority=priority)
                return jsonify({"total": len(forms), "forms": forms}), 200
            except Exception as exc:
                logger.error("Failed to list forms: %s", exc)
                return (
                    jsonify({"error": "Database unavailable.", "details": str(exc)}),
                    503,
                )

        @self.app.route("/forms/<form_id>", methods=["GET"])
        def get_form(form_id: str):
            try:
                result = self._db.get_form(form_id)
                if result is None:
                    return jsonify({"error": "Form not found."}), 404
                return jsonify(result), 200
            except Exception as exc:
                logger.error("Failed to get form: %s", exc)
                return (
                    jsonify({"error": "Database unavailable.", "details": str(exc)}),
                    503,
                )