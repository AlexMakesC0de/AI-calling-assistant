"""HTTP routes for the transcriber service."""

import logging
import tempfile
from pathlib import Path

from flask import Blueprint, jsonify, request

from audio_convert import prepare_for_transcription
from config import NUM_SPEAKERS
from diarization import assign_speakers, load_audio
from transcribe import transcribe_with_timestamps
from transcript import (
    build_diarized_transcript,
    build_plain_transcript,
    build_segments,
)

logger = logging.getLogger(__name__)

bp = Blueprint("transcriber", __name__)

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@bp.route("/health", methods=["GET"])
def health():
    """Liveness / readiness probe."""
    return jsonify({"status": "ok"}), 200


@bp.route("/transcribe", methods=["POST"])
def transcribe():
    """Accept an audio file and return a diarized transcript.

    **Form-data**:
        - ``file``: Audio file (.wav, .mp3, .ogg, .flac, etc.)
        - ``num_speakers``: (optional) Expected number of speakers (default: 2)
        - ``diarize``: (optional) "true" or "false" (default: "true")
        - ``max_duration_seconds``: (optional) Only process the first N seconds

    **Response (JSON)**::

        {
            "text": "Speaker 1: Hello... Speaker 2: Hi...",
            "plain_text": "Hello... Hi...",
            "word_count": 130,
            "speakers_detected": 2,
            "diarized": true,
            "detected_language": "en",
            "language_probability": 0.93,
            "segments": [
                {"speaker": 1, "text": "Hello...", "start": 0.0, "end": 2.5},
                ...
            ]
        }
    """
    if "file" not in request.files:
        return jsonify({"error": "No file part in the request."}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No file selected."}), 400

    num_speakers = int(request.form.get("num_speakers", NUM_SPEAKERS))
    do_diarize = request.form.get("diarize", "true").lower() == "true"
    max_duration_raw = request.form.get("max_duration_seconds")
    max_duration_seconds = None
    if max_duration_raw:
        try:
            parsed = float(max_duration_raw)
            if parsed > 0:
                max_duration_seconds = parsed
        except ValueError:
            pass

    # Save to temp file
    suffix = Path(file.filename).suffix or ".wav"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        file.save(tmp)
        tmp_path = tmp.name

    # Normalise Ogg/Opus (e.g. WhatsApp voice notes) to 16kHz mono PCM WAV —
    # Whisper's native format and a consistent waveform for the diarization
    # path. The original upload is preserved; converted_path is cleaned up
    # alongside it. (ISR-350)
    process_path, converted_path = prepare_for_transcription(tmp_path)

    try:
        # Step 1: Transcribe with word timestamps
        logger.info("Transcribing '%s'...", file.filename)
        words, detected_language, language_probability = transcribe_with_timestamps(
            process_path,
            max_duration_seconds=max_duration_seconds,
        )

        if not words:
            return jsonify({
                "text": "",
                "plain_text": "",
                "word_count": 0,
                "speakers_detected": 0,
                "diarized": False,
                "detected_language": detected_language,
                "language_probability": language_probability,
                "segments": [],
            }), 200

        plain_text = build_plain_transcript(words)

        if do_diarize and len(words) >= 5:
            try:
                # Step 2: Load audio for speaker embeddings
                logger.info("Loading audio for diarization...")
                waveform, sample_rate = load_audio(process_path)

                # Step 3: Assign speakers
                logger.info(
                    "Running speaker diarization (%d expected speakers)...",
                    num_speakers,
                )
                words = assign_speakers(words, waveform, sample_rate, num_speakers)

                # Step 4: Build diarized transcript
                diarized_text = build_diarized_transcript(words)
                speakers_detected = len(set(w.get("speaker", 1) for w in words))

                # Build segment list
                segments = build_segments(words)
            except Exception as exc:
                logger.warning(
                    "Diarization failed for %s, falling back to plain transcript: %s",
                    file.filename,
                    exc,
                )
                diarized_text = plain_text
                speakers_detected = 1
                segments = [{
                    "speaker": 1,
                    "text": plain_text,
                    "start": words[0]["start"],
                    "end": words[-1]["end"],
                }]
        else:
            diarized_text = plain_text
            speakers_detected = 1
            segments = [{
                "speaker": 1,
                "text": plain_text,
                "start": words[0]["start"],
                "end": words[-1]["end"],
            }]

        result = {
            "text": diarized_text,
            "plain_text": plain_text,
            "word_count": len(words),
            "speakers_detected": speakers_detected,
            "diarized": do_diarize and speakers_detected > 1,
            "detected_language": detected_language,
            "language_probability": language_probability,
            "segments": segments,
        }

        logger.info(
            "Transcription complete: %d words, %d speakers detected",
            len(words),
            speakers_detected,
        )
        return jsonify(result), 200

    except Exception as exc:
        logger.error("Transcription failed: %s", exc, exc_info=True)
        return jsonify({"error": str(exc)}), 500

    finally:
        Path(tmp_path).unlink(missing_ok=True)
        if converted_path:
            Path(converted_path).unlink(missing_ok=True)
