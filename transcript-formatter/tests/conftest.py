"""Pytest conftest for the transcript-formatter test suite.

Adds the formatter source directory to ``sys.path`` so the flat-import
modules (``config``, ``output_filters`` etc.) can be imported by test files
under ``tests/`` without packaging the service.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
