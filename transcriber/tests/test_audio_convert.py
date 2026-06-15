"""
Tests for audio_convert (ISR-350): Ogg/Opus -> 16kHz mono PCM WAV.

These exercise the real ffmpeg binary (the transcriber image ships it). When
ffmpeg is unavailable the suite skips rather than failing, so it never blocks
a machine without it. WAV format is validated with the stdlib ``wave`` module
to avoid pulling in soundfile/torch for a unit test.
"""

from __future__ import annotations

import shutil
import subprocess
import time
import wave
from pathlib import Path

import pytest

import audio_convert as ac

pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None, reason="ffmpeg not installed"
)


def _make_ogg_opus(path: Path, seconds: float = 2.0, freq: int = 440) -> None:
    """Synthesize a short Ogg/Opus tone with ffmpeg (a stand-in voice note)."""
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", f"sine=frequency={freq}:duration={seconds}",
            "-c:a", "libopus",
            str(path),
        ],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True,
    )


def _wav_params(path: Path) -> wave._wave_params:
    with wave.open(str(path), "rb") as w:
        return w.getparams()


# --- needs_conversion -------------------------------------------------------

@pytest.mark.parametrize("name,expected", [
    ("note.ogg", True),
    ("note.opus", True),
    ("note.oga", True),
    ("NOTE.OGG", True),       # case-insensitive
    ("call.wav", False),
    ("call.mp3", False),
    ("call.flac", False),
    ("noext", False),
])
def test_needs_conversion(name, expected):
    assert ac.needs_conversion(name) is expected


# --- convert_to_wav ---------------------------------------------------------

def test_convert_produces_16k_mono_pcm16_wav(tmp_path):
    src = tmp_path / "voice.ogg"
    _make_ogg_opus(src)

    dst = Path(ac.convert_to_wav(src))

    assert dst.is_file()
    params = _wav_params(dst)
    assert params.framerate == 16000          # Whisper's native rate
    assert params.nchannels == 1              # mono
    assert params.sampwidth == 2              # 16-bit PCM
    assert params.nframes > 0


def test_convert_preserves_original(tmp_path):
    src = tmp_path / "voice.ogg"
    _make_ogg_opus(src)
    original_bytes = src.read_bytes()

    ac.convert_to_wav(src)

    assert src.is_file(), "source must not be deleted"
    assert src.read_bytes() == original_bytes, "source must not be mutated"


def test_convert_default_dst_is_sibling_wav(tmp_path):
    src = tmp_path / "voice.ogg"
    _make_ogg_opus(src)

    dst = Path(ac.convert_to_wav(src))

    assert dst.parent == src.parent
    assert dst.name == "voice.wav"


def test_convert_within_five_second_budget(tmp_path):
    """AC: conversion completes in under 5s for a typical voice note."""
    src = tmp_path / "voice.ogg"
    _make_ogg_opus(src, seconds=8.0)  # generous: longer than a typical note

    start = time.monotonic()
    ac.convert_to_wav(src)
    elapsed = time.monotonic() - start

    assert elapsed < 5.0, f"conversion took {elapsed:.2f}s (budget 5s)"


def test_convert_wav_source_does_not_clobber(tmp_path):
    # A .wav source should be converted to a distinct file, not overwritten.
    src_ogg = tmp_path / "voice.ogg"
    _make_ogg_opus(src_ogg)
    src_wav = Path(ac.convert_to_wav(src_ogg))  # make a real wav first

    out = Path(ac.convert_to_wav(src_wav))

    assert out != src_wav
    assert out.name == "voice.converted.wav"
    assert src_wav.is_file()


def test_convert_missing_source_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        ac.convert_to_wav(tmp_path / "does_not_exist.ogg")


def test_convert_garbage_input_raises(tmp_path):
    bad = tmp_path / "broken.ogg"
    bad.write_bytes(b"this is not audio")
    with pytest.raises(ac.AudioConversionError):
        ac.convert_to_wav(bad)


# --- prepare_for_transcription ---------------------------------------------

def test_prepare_converts_ogg_and_reports_path(tmp_path):
    src = tmp_path / "voice.ogg"
    _make_ogg_opus(src)

    use_path, converted = ac.prepare_for_transcription(src)

    assert converted is not None
    assert use_path == converted
    assert Path(use_path).suffix == ".wav"
    assert _wav_params(Path(use_path)).framerate == 16000


def test_prepare_passes_through_wav(tmp_path):
    src = tmp_path / "call.wav"
    # a real wav so the path is plausible; content irrelevant to the branch
    _make_ogg_opus(tmp_path / "seed.ogg")
    shutil.copy(ac.convert_to_wav(tmp_path / "seed.ogg"), src)

    use_path, converted = ac.prepare_for_transcription(src)

    assert converted is None
    assert use_path == str(src)


def test_prepare_falls_back_on_conversion_failure(tmp_path):
    # Garbage .ogg: needs_conversion is True but ffmpeg fails -> fall back to
    # the original path, never raise (Whisper can still try its own decoder).
    bad = tmp_path / "broken.opus"
    bad.write_bytes(b"not audio")

    use_path, converted = ac.prepare_for_transcription(bad)

    assert converted is None
    assert use_path == str(bad)
