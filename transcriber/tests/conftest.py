"""Pytest path setup for the transcriber test suite.

Puts the transcriber source dir on sys.path so the flat-import modules
(``audio_convert`` etc.) import without packaging the service.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
