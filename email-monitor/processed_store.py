"""Persist processed email message IDs across restarts (ISR-241)."""

import json
import logging
import os
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_store_path = Path(
    os.getenv("PROCESSED_EMAILS_STORE", "/storage/processed_message_ids.json")
)


def _ensure_parent() -> None:
    try:
        _store_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        logger.warning("Could not create processed store dir: %s", exc)


def load_processed_ids() -> set[str]:
    _ensure_parent()
    if not _store_path.exists():
        return set()
    try:
        data = json.loads(_store_path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return set(str(item) for item in data)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Could not read processed store (%s); starting fresh", exc)
    return set()


def save_processed_ids(ids: set[str]) -> None:
    _ensure_parent()
    try:
        _store_path.write_text(
            json.dumps(sorted(ids), indent=2),
            encoding="utf-8",
        )
    except OSError as exc:
        logger.error("Failed to persist processed message IDs: %s", exc)


class ProcessedEmailStore:
    """Thread-safe store of Graph/IMAP message IDs already handled."""

    def __init__(self) -> None:
        with _lock:
            self._ids = load_processed_ids()

    def contains(self, message_id: str) -> bool:
        if not message_id:
            return False
        with _lock:
            return message_id in self._ids

    def mark_processed(self, message_id: str) -> None:
        if not message_id:
            return
        with _lock:
            if message_id in self._ids:
                return
            self._ids.add(message_id)
            save_processed_ids(self._ids)
        logger.info("Marked message_id=%s as processed (total=%d)", message_id, len(self._ids))
