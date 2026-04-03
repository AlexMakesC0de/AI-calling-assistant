import json
from datetime import datetime, timezone
from pathlib import Path

from config import EVENTS_DIR
from util import safe_stem


def save_event(event: dict) -> Path:
    event_id = str(event.get("event_id") or event.get("call_id") or datetime.now(timezone.utc).timestamp())
    event_file = EVENTS_DIR / f"{safe_stem(event_id)}.json"
    with event_file.open("w", encoding="utf-8") as f:
        json.dump(event, f, ensure_ascii=False, indent=2)
    return event_file
