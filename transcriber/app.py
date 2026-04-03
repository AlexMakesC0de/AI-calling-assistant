"""
Transcriber Service (with Speaker Diarization)
================================================
Accepts audio files and returns a transcript with speaker labels.

Uses:
  - **faster-whisper** for speech-to-text with word-level timestamps
  - **speechbrain** ECAPA-TDNN embeddings for speaker identification
  - **spectral clustering** to group speech segments by speaker

The result is a labeled transcript like:
    Speaker 1: Hello, how can I help you?
    Speaker 2: Hi, I have a problem with my account.

This dramatically improves the AI form-filler's ability to identify
who is the agent and who is the caller.
"""

from flask import Flask

# Side effect: loads Whisper + SpeechBrain once per worker (gunicorn import path).
import models  # noqa: F401
from routes import bp

app = Flask(__name__)
app.register_blueprint(bp)

# ---------------------------------------------------------------------------
# Entrypoint (development only – production uses gunicorn)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=9000, debug=True)
