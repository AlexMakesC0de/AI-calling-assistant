import logging
import re
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
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
        self._executor = ThreadPoolExecutor(max_workers=4)

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
            include_dutch_raw = str(
                request.form.get("include_dutch_translation", "")
            ).strip().lower()
            if include_dutch_raw in {"true", "false", "1", "0", "yes", "no", "on", "off"}:
                caller_metadata["include_dutch_translation"] = include_dutch_raw
            caller_metadata = {k: v for k, v in caller_metadata.items() if v}

            logger.info("Step 1: Transcribing %s via Whisper...", filename)
            try:
                transcription = self._clients.transcribe(filepath)
                transcript_text = transcription.get("text", "")
                alpha_chars = len(re.findall(r"[A-Za-z]", transcript_text))
                result["pipeline"]["transcription"] = {
                    "status": "success",
                    "text": transcript_text,
                    "word_count": len(transcript_text.split()),
                }
                if alpha_chars < 6:
                    result["pipeline"]["transcription"]["quality_warning"] = (
                        "Transcript content is too short/noisy for reliable translation. "
                        "Try a clearer recording or a larger Whisper model."
                    )
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

            email_future = self._executor.submit(self._clients.send_email, email_payload)

            logger.info("Step 4: Storing form in database...")
            db_future = self._executor.submit(
                self._db.store_upload_with_form,
                form=completed_form,
                audio_filename=filename,
                audio_path=str(filepath),
                transcript_text=transcript_text,
                completed_at=completed_form.get("completed_at"),
                source_lang=transcription.get("detected_language"),
            )

            try:
                storage_result = db_future.result(timeout=self._config.db_save_wait_seconds)
                if storage_result:
                    result["pipeline"]["database"] = {
                        "status": "stored",
                        "incident_form": "stored",
                        "storage_projection": "stored",
                        **storage_result,
                    }
                else:
                    result["pipeline"]["database"] = {
                        "status": "failed",
                        "incident_form": "failed",
                        "storage_projection": "failed",
                    }
            except FutureTimeoutError:
                logger.warning(
                    "Database save exceeded %ss wait window; continuing in background.",
                    self._config.db_save_wait_seconds,
                )
                result["pipeline"]["database"] = {
                    "status": "processing",
                    "incident_form": "processing",
                    "storage_projection": "processing",
                    "note": "Database save continues in background.",
                }
            except Exception as exc:
                logger.error("Database save failed: %s", exc)
                result["pipeline"]["database"] = {
                    "status": "failed",
                    "incident_form": "failed",
                    "storage_projection": "failed",
                    "error": str(exc),
                }

            try:
                email_future.result(timeout=45)
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

            translated_nl = completed_form.get("translated_nl", {})
            if isinstance(translated_nl, dict):
                result["pipeline"]["transcripts"] = {
                    "original": transcript_text,
                    "dutch": translated_nl.get("transcript_text", ""),
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

        @self.app.route("/email-notifications", methods=["GET"])
        def get_email_notifications():
            """Proxy to email-monitor service to get notifications."""
            try:
                import requests
                email_monitor_url = "http://email-monitor:5003/notifications"
                response = requests.get(email_monitor_url, timeout=5)
                response.raise_for_status()
                return jsonify(response.json()), 200
            except requests.exceptions.ConnectionError:
                logger.warning("Email monitor service not available")
                return jsonify({"notifications": []}), 200
            except Exception as exc:
                logger.error("Failed to get email notifications: %s", exc)
                return jsonify({"notifications": []}), 200

        @self.app.route("/email-notifications/clear", methods=["POST"])
        def clear_email_notifications():
            """Proxy to email-monitor service to clear notifications."""
            try:
                import requests
                email_monitor_url = "http://email-monitor:5003/notifications/clear"
                response = requests.post(email_monitor_url, timeout=5)
                response.raise_for_status()
                return jsonify(response.json()), 200
            except requests.exceptions.ConnectionError:
                logger.warning("Email monitor service not available")
                return jsonify({"status": "cleared"}), 200
            except Exception as exc:
                logger.error("Failed to clear email notifications: %s", exc)
                return jsonify({"status": "cleared"}), 200

        @self.app.route("/emails", methods=["GET"])
        def emails_dashboard():
            """Serve the email notifications dashboard page."""
            return render_template("emails.html")
