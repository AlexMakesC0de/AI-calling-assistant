"""Environment-driven settings and logging for the transcriber service."""

import logging
import os

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "small")
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "cpu")
WHISPER_COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
NUM_SPEAKERS = int(os.getenv("NUM_SPEAKERS", "2"))  # default: 2 (agent + caller)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s – %(message)s",
)
