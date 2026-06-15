"""Load Whisper and SpeechBrain models once per worker process.

Both models are fetched from the Hugging Face Hub on first use. To survive
slow / intermittent connections, the downloads go through the resilient,
resumable retry helpers in :mod:`model_loader` rather than relying on each
library's single-attempt default.
"""

import logging

import torch
from faster_whisper import WhisperModel
from speechbrain.inference.speaker import EncoderClassifier

from config import (
    MODEL_DOWNLOAD_BASE_DELAY,
    MODEL_DOWNLOAD_MAX_ATTEMPTS,
    MODEL_DOWNLOAD_MAX_DELAY,
    WHISPER_COMPUTE_TYPE,
    WHISPER_DEVICE,
    WHISPER_MODEL_SIZE,
)
from model_loader import download_whisper_snapshot, run_with_download_retry

logger = logging.getLogger(__name__)

_SPEAKER_ENCODER_SOURCE = "speechbrain/spkrec-ecapa-voxceleb"
_SPEAKER_ENCODER_SAVEDIR = "/models/speechbrain"

# Shared retry budget for every model download in this module.
_DOWNLOAD_RETRY_KWARGS = {
    "max_attempts": MODEL_DOWNLOAD_MAX_ATTEMPTS,
    "base_delay_seconds": MODEL_DOWNLOAD_BASE_DELAY,
    "max_delay_seconds": MODEL_DOWNLOAD_MAX_DELAY,
}

device = WHISPER_DEVICE
compute_type = WHISPER_COMPUTE_TYPE
if device.startswith("cuda") and not torch.cuda.is_available():
    logger.warning("CUDA requested but not available — falling back to CPU")
    device = "cpu"
    compute_type = "int8"

# SpeechBrain requires "cuda:N" format; normalise bare "cuda" → "cuda:0"
sb_device = "cuda:0" if device == "cuda" else device

# Pre-fetch the Whisper snapshot with resumable retries, then load from the
# local path. Passing a directory (not a size alias) guarantees WhisperModel
# does no network I/O of its own — all download resilience lives in one place.
whisper_model_path = download_whisper_snapshot(
    WHISPER_MODEL_SIZE,
    **_DOWNLOAD_RETRY_KWARGS,
)

logger.info(
    "Loading Whisper model '%s' on %s (%s)...",
    WHISPER_MODEL_SIZE,
    device,
    compute_type,
)
whisper_model = WhisperModel(
    whisper_model_path,
    device=device,
    compute_type=compute_type,
)
logger.info("Whisper model loaded.")

# SpeechBrain has no separate snapshot step we can pre-stage, so we retry the
# loader itself; from_hparams resumes cached files, so retries are safe.
logger.info("Loading SpeechBrain speaker encoder...")
speaker_model = run_with_download_retry(
    lambda: EncoderClassifier.from_hparams(
        source=_SPEAKER_ENCODER_SOURCE,
        savedir=_SPEAKER_ENCODER_SAVEDIR,
        run_opts={"device": sb_device},
    ),
    description="SpeechBrain speaker encoder download",
    **_DOWNLOAD_RETRY_KWARGS,
)
logger.info("Speaker encoder loaded.")
