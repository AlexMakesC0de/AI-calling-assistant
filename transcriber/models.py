"""Load Whisper and SpeechBrain models once per worker process."""

import logging

import torch
from faster_whisper import WhisperModel
from speechbrain.inference.speaker import EncoderClassifier

from config import WHISPER_COMPUTE_TYPE, WHISPER_DEVICE, WHISPER_MODEL_SIZE

logger = logging.getLogger(__name__)

device = WHISPER_DEVICE
compute_type = WHISPER_COMPUTE_TYPE
if device.startswith("cuda") and not torch.cuda.is_available():
    logger.warning("CUDA requested but not available — falling back to CPU")
    device = "cpu"
    compute_type = "int8"

# SpeechBrain requires "cuda:N" format; normalise bare "cuda" → "cuda:0"
sb_device = "cuda:0" if device == "cuda" else device

logger.info(
    "Loading Whisper model '%s' on %s (%s)...",
    WHISPER_MODEL_SIZE,
    device,
    compute_type,
)
whisper_model = WhisperModel(
    WHISPER_MODEL_SIZE,
    device=device,
    compute_type=compute_type,
)
logger.info("Whisper model loaded.")

logger.info("Loading SpeechBrain speaker encoder...")
speaker_model = EncoderClassifier.from_hparams(
    source="speechbrain/spkrec-ecapa-voxceleb",
    savedir="/models/speechbrain",
    run_opts={"device": sb_device},
)
logger.info("Speaker encoder loaded.")
