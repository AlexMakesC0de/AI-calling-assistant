"""faster-whisper transcription with approximate word-level timings."""

import logging
import re

from config import WHISPER_HINTS
from models import whisper_model

logger = logging.getLogger(__name__)

_REPAK_RE = re.compile(r"\b(?:rapack|repack|re-pak)\b", re.IGNORECASE)


def _normalize_repak(words: list[dict]) -> list[dict]:
    """Replace misheard "Repak" variants in each word token with "Repak"."""
    for word in words:
        token = word.get("word")
        if isinstance(token, str):
            word["word"] = _REPAK_RE.sub("Repak", token)
    return words

# ---------------------------------------------------------------------------
# Core logic – Whisper
# ---------------------------------------------------------------------------


def transcribe_with_timestamps(
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
        "beam_size": 3,
        "condition_on_previous_text": False,
    }
    if max_duration_seconds is not None and max_duration_seconds > 0:
        transcribe_kwargs["clip_timestamps"] = [0, float(max_duration_seconds)]

    if WHISPER_HINTS:
        transcribe_kwargs["initial_prompt"] = ", ".join(WHISPER_HINTS)

    segments, info = whisper_model.transcribe(audio_path, **transcribe_kwargs)
    logger.info(
        "Detected language: %s (probability: %.2f)",
        info.language,
        info.language_probability,
    )

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
    words = _normalize_repak(words)
    detected_language = getattr(info, "language", None)
    language_probability = getattr(info, "language_probability", None)
    return words, detected_language, language_probability
