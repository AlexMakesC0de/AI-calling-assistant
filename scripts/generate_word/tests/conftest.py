"""Pytest path setup so `generate_word` imports without packaging the script."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
