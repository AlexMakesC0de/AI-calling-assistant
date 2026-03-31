"""Voice app entrypoint and Flask app factory."""

from flask import Flask

from config import AppConfig
from webapp import VoiceRecordingApp


def create_app() -> Flask:
    """Application factory used by gunicorn and local development."""
    config = AppConfig.from_env()
    voice_app = VoiceRecordingApp(config)
    return voice_app.app


# Keep a module-level app for gunicorn compatibility (e.g. gunicorn app:app).
app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
