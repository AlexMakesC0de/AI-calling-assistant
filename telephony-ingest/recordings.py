from pathlib import Path

import requests

from config import (
    FORWARD_TIMEOUT,
    RECORDING_AUTH_HEADER,
    RECORDING_AUTH_VALUE,
    RECORDING_DOWNLOAD_TIMEOUT,
    TMP_DIR,
    VOICE_APP_UPLOAD_URL,
)
from util import safe_stem


def download_recording(recording_url: str, call_id: str) -> Path:
    out_file = TMP_DIR / f"{safe_stem(call_id)}.wav"
    headers = {}
    if RECORDING_AUTH_HEADER and RECORDING_AUTH_VALUE:
        headers[RECORDING_AUTH_HEADER] = RECORDING_AUTH_VALUE

    with requests.get(recording_url, stream=True, timeout=RECORDING_DOWNLOAD_TIMEOUT, headers=headers) as resp:
        resp.raise_for_status()
        with out_file.open("wb") as f:
            for chunk in resp.iter_content(chunk_size=1024 * 64):
                if chunk:
                    f.write(chunk)
    return out_file


def resolve_recording_path(event: dict) -> Path:
    local_path = event.get("recording_path")
    if local_path:
        path = Path(local_path)
        if not path.exists():
            raise FileNotFoundError(f"recording_path does not exist: {local_path}")
        return path

    recording_url = event.get("recording_url")
    if not recording_url:
        raise ValueError("event must include recording_url or recording_path")

    call_id = str(event.get("call_id") or event.get("event_id") or "call")
    return download_recording(recording_url, call_id)


def forward_to_voice_app(event: dict, recording_path: Path) -> dict:
    caller = str(event.get("caller_id") or "").strip()
    source = str(event.get("source_number") or "").strip()
    call_mode = "answered_call" if event.get("answered") else "voicemail"

    data = {
        "contact_info": caller,
        "account_or_reference": str(event.get("call_id") or ""),
        "telephony_source_number": source,
        "telephony_call_mode": call_mode,
        "telephony_provider": str(event.get("provider") or ""),
    }
    data = {k: v for k, v in data.items() if v}

    mime_types = {
        ".wav": "audio/wav",
        ".ogg": "audio/ogg",
        ".mp3": "audio/mpeg",
        ".gsm": "audio/x-gsm",
    }
    mime = mime_types.get(recording_path.suffix.lower(), "application/octet-stream")

    with recording_path.open("rb") as f:
        files = {"file": (recording_path.name, f, mime)}
        resp = requests.post(
            VOICE_APP_UPLOAD_URL,
            data=data,
            files=files,
            timeout=FORWARD_TIMEOUT,
        )
    resp.raise_for_status()
    return resp.json()
