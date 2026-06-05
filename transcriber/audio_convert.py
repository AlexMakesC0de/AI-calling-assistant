"""
Audio format normalisation for the transcriber service (ISR-350).

WhatsApp voice notes arrive as Ogg/Opus (``.ogg`` / ``.opus``). faster-whisper
can decode them via its bundled ffmpeg, but the diarization path
(``diarization.load_audio`` → ``soundfile.read``) relies on libsndfile, which
does not reliably decode Opus — so an un-converted voice note transcribes but
fails speaker diarization.

This module converts such inputs to the format Whisper and libsndfile both
handle natively: 16 kHz, mono, signed-16-bit PCM WAV. The original file is
always preserved — conversion writes a new ``.wav`` beside it and never
deletes or mutates the source.

ffmpeg is invoked as a subprocess (the binary already ships in the transcriber
image). No extra Python dependency is added.
"""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

# WhatsApp voice notes; ".oga" is the Ogg-audio variant some clients use.
OGG_OPUS_SUFFIXES = {".ogg", ".opus", ".oga"}

# Whisper's native input + what libsndfile reads without codec support.
TARGET_SAMPLE_RATE = 16000
TARGET_CHANNELS = 1

FFMPEG_BIN = os.getenv("FFMPEG_BIN", "ffmpeg")
# A typical voice note is seconds long and must convert in well under the 5s
# budget; the timeout only guards against a wedged ffmpeg process.
DEFAULT_TIMEOUT_SECONDS = float(os.getenv("AUDIO_CONVERT_TIMEOUT", "30"))


class AudioConversionError(RuntimeError):
    """Raised when ffmpeg fails to convert an audio file."""


def needs_conversion(path: str | os.PathLike) -> bool:
    """True when the file is an Ogg/Opus container that should be normalised.

    Scoped deliberately to Ogg/Opus: WAV/MP3/FLAC already decode cleanly in
    both faster-whisper and libsndfile, so converting them would only add
    latency.
    """
    return Path(path).suffix.lower() in OGG_OPUS_SUFFIXES


def convert_to_wav(
    src_path: str | os.PathLike,
    dst_path: str | os.PathLike | None = None,
    *,
    sample_rate: int = TARGET_SAMPLE_RATE,
    channels: int = TARGET_CHANNELS,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> str:
    """Convert any audio file to 16 kHz mono PCM-16 WAV via ffmpeg.

    The source file is left untouched. By default the WAV is written beside
    the source as ``<stem>.wav`` (``<stem>.converted.wav`` when the source is
    itself a ``.wav``, to avoid clobbering it).

    Returns the path to the written WAV.

    Raises
    ------
    FileNotFoundError
        If ``src_path`` does not exist.
    AudioConversionError
        If ffmpeg is missing, exits non-zero, or times out.
    """
    src = Path(src_path)
    if not src.is_file():
        raise FileNotFoundError(f"Audio file not found: {src}")

    if dst_path is None:
        stem = src.stem
        suffix = ".converted.wav" if src.suffix.lower() == ".wav" else ".wav"
        dst = src.with_name(f"{stem}{suffix}")
    else:
        dst = Path(dst_path)

    cmd = [
        FFMPEG_BIN,
        "-y",                       # overwrite dst if it exists
        "-i", str(src),
        "-ar", str(sample_rate),    # resample
        "-ac", str(channels),       # downmix to mono
        "-c:a", "pcm_s16le",        # signed 16-bit PCM
        "-f", "wav",
        str(dst),
    ]

    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:  # ffmpeg binary missing
        raise AudioConversionError(
            f"ffmpeg binary '{FFMPEG_BIN}' not found"
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise AudioConversionError(
            f"ffmpeg timed out after {timeout}s converting {src.name}"
        ) from exc

    if proc.returncode != 0 or not dst.is_file():
        stderr_tail = (proc.stderr or b"").decode("utf-8", "replace")[-500:]
        raise AudioConversionError(
            f"ffmpeg failed ({proc.returncode}) converting {src.name}: "
            f"{stderr_tail.strip()}"
        )

    logger.info("Converted %s -> %s (%d Hz, %d ch, PCM16)",
                src.name, dst.name, sample_rate, channels)
    return str(dst)


def prepare_for_transcription(src_path: str | os.PathLike) -> tuple[str, str | None]:
    """Normalise the input for transcription if it is Ogg/Opus.

    Returns ``(path_to_use, converted_path)``:
      * ``path_to_use`` is the WAV when a conversion happened, else the
        original ``src_path`` unchanged.
      * ``converted_path`` is the WAV that was created (so the caller can
        clean it up), or ``None`` when no conversion was needed.

    Never raises: on conversion failure it logs and falls back to the original
    path, so a flaky codec can't take down the transcription request — Whisper
    can still attempt the original via its own decoder.
    """
    if not needs_conversion(src_path):
        return str(src_path), None

    try:
        wav_path = convert_to_wav(src_path)
        return wav_path, wav_path
    except (AudioConversionError, FileNotFoundError) as exc:
        logger.warning(
            "Ogg/Opus conversion failed for %s; using original: %s",
            Path(src_path).name, exc,
        )
        return str(src_path), None
