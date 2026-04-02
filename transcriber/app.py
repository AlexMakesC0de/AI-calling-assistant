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

import io
import logging
import os
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
from faster_whisper import WhisperModel
from flask import Flask, jsonify, request
from scipy.signal import resample_poly
from sklearn.cluster import SpectralClustering
from speechbrain.inference.speaker import EncoderClassifier

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

app = Flask(__name__)

WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "small")
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "cpu")
WHISPER_COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
NUM_SPEAKERS = int(os.getenv("NUM_SPEAKERS", "2"))  # default: 2 (agent + caller)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s – %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Model loading (done once at startup)
# ---------------------------------------------------------------------------

logger.info("Loading Whisper model '%s' on %s (%s)...",
            WHISPER_MODEL_SIZE, WHISPER_DEVICE, WHISPER_COMPUTE_TYPE)
whisper_model = WhisperModel(
    WHISPER_MODEL_SIZE,
    device=WHISPER_DEVICE,
    compute_type=WHISPER_COMPUTE_TYPE,
)
logger.info("Whisper model loaded.")

logger.info("Loading SpeechBrain speaker encoder...")
speaker_model = EncoderClassifier.from_hparams(
    source="speechbrain/spkrec-ecapa-voxceleb",
    savedir="/models/speechbrain",
    run_opts={"device": WHISPER_DEVICE},
)
logger.info("Speaker encoder loaded.")


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------


def _transcribe_with_timestamps(
    audio_path: str,
    max_duration_seconds: float | None = None,
) -> tuple[list[dict], str | None, float | None]:
    """Run faster-whisper and return approximate word-level timings.

    Uses segment timestamps (stable on CPU) and distributes times across words
    inside each segment.

    Returns a list of dicts:
        [{"word": "Hello", "start": 0.0, "end": 0.5}, ...]
    """
    transcribe_kwargs = {
        "word_timestamps": False,
        "vad_filter": True,
        "beam_size": 1,
    }
    if max_duration_seconds is not None and max_duration_seconds > 0:
        transcribe_kwargs["clip_timestamps"] = [0, float(max_duration_seconds)]

    segments, info = whisper_model.transcribe(audio_path, **transcribe_kwargs)
    logger.info("Detected language: %s (probability: %.2f)",
                info.language, info.language_probability)

    words = []
    for segment in segments:
        segment_text = (segment.text or "").strip()
        if not segment_text:
            continue

        segment_words = segment_text.split()
        if not segment_words:
            continue

        start = float(segment.start or 0.0)
        end = float(segment.end or start)
        duration = max(0.01, end - start)
        step = duration / len(segment_words)

        for i, token in enumerate(segment_words):
            word_start = start + (i * step)
            word_end = start + ((i + 1) * step)
            words.append({
                "word": f" {token}",
                "start": word_start,
                "end": word_end,
            })
    detected_language = getattr(info, "language", None)
    language_probability = getattr(info, "language_probability", None)
    return words, detected_language, language_probability


def _load_audio(audio_path: str) -> tuple[torch.Tensor, int]:
    """Load audio file and resample to 16kHz mono."""
    audio, sample_rate = sf.read(audio_path, always_2d=False)

    if isinstance(audio, np.ndarray) and audio.ndim > 1:
        audio = np.mean(audio, axis=1)

    if sample_rate != 16000:
        audio = resample_poly(audio, 16000, sample_rate)
        sample_rate = 16000

    waveform = torch.tensor(audio, dtype=torch.float32).unsqueeze(0)
    return waveform, sample_rate


def _get_speaker_embedding(waveform: torch.Tensor, sample_rate: int,
                           start: float, end: float) -> np.ndarray | None:
    """Extract a speaker embedding for a time range from the audio.

    Returns None if the segment is too short (< 0.3s).
    """
    start_sample = int(start * sample_rate)
    end_sample = int(end * sample_rate)

    # Need at least 0.3 seconds for a reliable embedding
    if (end_sample - start_sample) < int(0.3 * sample_rate):
        return None

    segment = waveform[:, start_sample:end_sample]
    if segment.shape[1] == 0:
        return None

    with torch.no_grad():
        embedding = speaker_model.encode_batch(segment)
    return embedding.squeeze().cpu().numpy()


def _assign_speakers(words: list[dict], waveform: torch.Tensor,
                     sample_rate: int, num_speakers: int) -> list[dict]:
    """Assign a speaker label to each word using speaker embeddings
    and spectral clustering.

    Groups consecutive words into chunks (~2-3 seconds each) to get
    reliable speaker embeddings, then clusters the embeddings.
    """
    if not words:
        return words

    # Group words into chunks for more reliable embeddings
    chunks = []
    current_chunk = {"words": [], "start": words[0]["start"], "end": words[0]["end"]}

    for i, word in enumerate(words):
        current_chunk["words"].append(word)
        current_chunk["end"] = word["end"]

        # Create a new chunk every ~2.5 seconds or on long pauses
        chunk_duration = current_chunk["end"] - current_chunk["start"]
        next_idx = i + 1
        gap = (words[next_idx]["start"] - word["end"]) if next_idx < len(words) else 999

        if chunk_duration >= 2.5 or gap > 1.0:
            chunks.append(current_chunk)
            if next_idx < len(words):
                current_chunk = {
                    "words": [],
                    "start": words[next_idx]["start"],
                    "end": words[next_idx]["start"],
                }
            else:
                current_chunk = {"words": [], "start": 0, "end": 0}

    # Don't forget the last chunk
    if current_chunk["words"]:
        chunks.append(current_chunk)

    logger.info("Created %d chunks for speaker embedding", len(chunks))

    # Extract embeddings for each chunk
    embeddings = []
    valid_chunks = []
    for chunk in chunks:
        emb = _get_speaker_embedding(waveform, sample_rate,
                                     chunk["start"], chunk["end"])
        if emb is not None:
            embeddings.append(emb)
            valid_chunks.append(chunk)

    if len(embeddings) < 2:
        # Not enough data to cluster — assign all to Speaker 1
        logger.warning("Not enough chunks for clustering (%d). Assigning all to Speaker 1.", len(embeddings))
        for word in words:
            word["speaker"] = 1
        return words

    # Cluster embeddings
    embedding_matrix = np.array(embeddings)
    n_clusters = min(num_speakers, len(embeddings))

    try:
        clustering = SpectralClustering(
            n_clusters=n_clusters,
            affinity="cosine",
            random_state=42,
        )
        labels = clustering.fit_predict(embedding_matrix)
    except Exception as exc:
        logger.warning("Spectral clustering failed, falling back to simple assignment: %s", exc)
        # Fallback: alternate speakers on pauses
        for word in words:
            word["speaker"] = 1
        return words

    # Assign speaker labels to each word based on its chunk
    for chunk, label in zip(valid_chunks, labels):
        for word in chunk["words"]:
            word["speaker"] = int(label) + 1  # 1-indexed

    # Fill in any words without a speaker (from invalid chunks)
    last_speaker = 1
    for word in words:
        if "speaker" not in word:
            word["speaker"] = last_speaker
        else:
            last_speaker = word["speaker"]

    return words


def _build_diarized_transcript(words: list[dict]) -> str:
    """Build a readable transcript with speaker labels.

    Output format:
        Speaker 1: Hello, how can I help you today?
        Speaker 2: Hi, I have a problem with my account.
    """
    if not words:
        return ""

    lines = []
    current_speaker = None
    current_text = []

    for word in words:
        speaker = word.get("speaker", 1)
        if speaker != current_speaker:
            # Save previous line
            if current_text:
                lines.append(f"Speaker {current_speaker}: {''.join(current_text).strip()}")
            current_speaker = speaker
            current_text = [word["word"]]
        else:
            current_text.append(word["word"])

    # Don't forget the last line
    if current_text:
        lines.append(f"Speaker {current_speaker}: {''.join(current_text).strip()}")

    return "\n".join(lines)


def _build_plain_transcript(words: list[dict]) -> str:
    """Build a plain transcript without speaker labels (fallback)."""
    return " ".join(w["word"] for w in words).strip()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.route("/health", methods=["GET"])
def health():
    """Liveness / readiness probe."""
    return jsonify({"status": "ok"}), 200


@app.route("/transcribe", methods=["POST"])
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

    try:
        # Step 1: Transcribe with word timestamps
        logger.info("Transcribing '%s'...", file.filename)
        words, detected_language, language_probability = _transcribe_with_timestamps(
            tmp_path,
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

        plain_text = _build_plain_transcript(words)

        if do_diarize and len(words) >= 5:
            try:
                # Step 2: Load audio for speaker embeddings
                logger.info("Loading audio for diarization...")
                waveform, sample_rate = _load_audio(tmp_path)

                # Step 3: Assign speakers
                logger.info("Running speaker diarization (%d expected speakers)...",
                            num_speakers)
                words = _assign_speakers(words, waveform, sample_rate, num_speakers)

                # Step 4: Build diarized transcript
                diarized_text = _build_diarized_transcript(words)
                speakers_detected = len(set(w.get("speaker", 1) for w in words))

                # Build segment list
                segments = _build_segments(words)
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
            segments = [{"speaker": 1, "text": plain_text,
                        "start": words[0]["start"], "end": words[-1]["end"]}]

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

        logger.info("Transcription complete: %d words, %d speakers detected",
                    len(words), speakers_detected)
        return jsonify(result), 200

    except Exception as exc:
        logger.error("Transcription failed: %s", exc, exc_info=True)
        return jsonify({"error": str(exc)}), 500

    finally:
        Path(tmp_path).unlink(missing_ok=True)


def _build_segments(words: list[dict]) -> list[dict]:
    """Group consecutive words by speaker into segments."""
    if not words:
        return []

    segments = []
    current = {
        "speaker": words[0].get("speaker", 1),
        "text_parts": [words[0]["word"]],
        "start": words[0]["start"],
        "end": words[0]["end"],
    }

    for word in words[1:]:
        if word.get("speaker", 1) == current["speaker"]:
            current["text_parts"].append(word["word"])
            current["end"] = word["end"]
        else:
            segments.append({
                "speaker": current["speaker"],
                "text": "".join(current["text_parts"]).strip(),
                "start": round(current["start"], 2),
                "end": round(current["end"], 2),
            })
            current = {
                "speaker": word.get("speaker", 1),
                "text_parts": [word["word"]],
                "start": word["start"],
                "end": word["end"],
            }

    segments.append({
        "speaker": current["speaker"],
        "text": "".join(current["text_parts"]).strip(),
        "start": round(current["start"], 2),
        "end": round(current["end"], 2),
    })

    return segments


# ---------------------------------------------------------------------------
# Entrypoint (development only – production uses gunicorn)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=9000, debug=True)
