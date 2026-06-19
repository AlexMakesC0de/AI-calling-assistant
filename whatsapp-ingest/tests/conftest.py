"""Pytest path setup for the whatsapp-ingest test suite."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
