"""Environment-driven settings and logging for the transcriber service."""

import logging
import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "small")
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "cpu")
WHISPER_COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
NUM_SPEAKERS = int(os.getenv("NUM_SPEAKERS", "2"))  # default: 2 (agent + caller)

# ---------------------------------------------------------------------------
# Recognition hints
# ---------------------------------------------------------------------------
# Proper nouns (company/people/product names) that Whisper would otherwise
# mishear are loaded from hints.txt and fed to the model as an initial_prompt.

_BASE_DIR = Path(__file__).parent


def _load_lines(filename: str) -> list[str]:
    """Return non-empty, non-comment lines from a sidecar text file.

    A missing file yields an empty list so the service still starts when no
    hints are configured.
    """
    path = _BASE_DIR / filename
    if not path.exists():
        return []
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


WHISPER_HINTS: list[str] = _load_lines("hints.txt")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s – %(message)s",
)
