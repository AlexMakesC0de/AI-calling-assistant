"""Load Whisper and SpeechBrain models once per worker process."""

import logging

from faster_whisper import WhisperModel
from speechbrain.inference.speaker import EncoderClassifier

from config import WHISPER_COMPUTE_TYPE, WHISPER_DEVICE, WHISPER_MODEL_SIZE

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Model loading (done once at startup)
# ---------------------------------------------------------------------------

logger.info(
    "Loading Whisper model '%s' on %s (%s)...",
    WHISPER_MODEL_SIZE,
    WHISPER_DEVICE,
    WHISPER_COMPUTE_TYPE,
)
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
