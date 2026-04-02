"""
AMI CDR Listener — watches for completed call recordings and forwards
them to the telephony-ingest webhook for processing through the pipeline.

Connects to Asterisk Manager Interface (AMI), listens for Cdr events
with a non-empty recordingfile, then POST the event to the webhook.
"""

import logging
import os
import socket
import time

import requests

logger = logging.getLogger(__name__)

AMI_HOST = os.getenv("AMI_HOST", "freepbx")
AMI_PORT = int(os.getenv("AMI_PORT", "5038"))
AMI_USER = os.getenv("AMI_USER", "admin-docker")
AMI_PASS = os.getenv("AMI_PASS", "amp111")
WEBHOOK_URL = os.getenv(
    "WEBHOOK_URL", "http://localhost:5010/webhooks/recording-complete"
)
WEBHOOK_TOKEN = os.getenv("TELEPHONY_WEBHOOK_TOKEN", "")
RECORDING_BASE = os.getenv("RECORDING_BASE", "/data/pbx-recordings")
RECONNECT_DELAY = int(os.getenv("AMI_RECONNECT_DELAY", "10"))
WEBHOOK_TIMEOUT = int(os.getenv("WEBHOOK_TIMEOUT", "300"))


def _ami_connect() -> socket.socket:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(30)
    sock.connect((AMI_HOST, AMI_PORT))
    banner = sock.recv(1024).decode("utf-8", errors="replace")
    logger.info("AMI banner: %s", banner.strip())

    login = (
        f"Action: Login\r\n"
        f"Username: {AMI_USER}\r\n"
        f"Secret: {AMI_PASS}\r\n"
        f"\r\n"
    )
    sock.sendall(login.encode())
    resp = sock.recv(4096).decode("utf-8", errors="replace")
    if "Success" not in resp:
        raise ConnectionError(f"AMI login failed: {resp.strip()}")
    logger.info("AMI login successful")
    return sock


def _parse_events(buf: str) -> tuple[list[dict], str]:
    events = []
    while "\r\n\r\n" in buf:
        block, buf = buf.split("\r\n\r\n", 1)
        event = {}
        for line in block.split("\r\n"):
            if ": " in line:
                key, val = line.split(": ", 1)
                event[key] = val
        if event:
            events.append(event)
    return events, buf


def _build_webhook_payload(cdr: dict) -> dict | None:
    # The field comes from cdr_manager mapping: recordingfile => recordingfile
    recording_file = (cdr.get("recordingfile") or cdr.get("RecordFile", "")).strip()
    if not recording_file:
        return None

    disposition = cdr.get("Disposition", "").upper()
    duration = int(cdr.get("Duration", "0"))
    billsec = int(cdr.get("BillableSeconds", "0"))

    if duration < 3:
        logger.debug("Skipping short call (%ss): %s", duration, recording_file)
        return None

    # Build the full path using date from StartTime.
    # CDR recordingfile is just the filename (e.g. in-9999-1002-20260402-163558.ogg)
    # Actual path: /var/spool/asterisk/monitor/YYYY/MM/DD/<filename>
    start_time = cdr.get("StartTime", "")
    date_path = ""
    if start_time:
        # StartTime format: "2026-04-02 16:35:58"
        date_part = start_time.split(" ")[0] if " " in start_time else start_time[:10]
        parts = date_part.split("-")
        if len(parts) == 3:
            date_path = f"{parts[0]}/{parts[1]}/{parts[2]}"

    if date_path:
        recording_path = f"{RECORDING_BASE}/{date_path}/{recording_file}"
    else:
        recording_path = f"{RECORDING_BASE}/{recording_file}"

    return {
        "provider": "freepbx",
        "event_id": cdr.get("UniqueID", ""),
        "call_id": cdr.get("UniqueID", ""),
        "source_number": cdr.get("Source", ""),
        "destination_number": cdr.get("Destination", ""),
        "caller_id": cdr.get("CallerID", ""),
        "answered": disposition == "ANSWERED",
        "recording_path": recording_path,
        "started_at": cdr.get("StartTime", ""),
        "ended_at": cdr.get("EndTime", ""),
        "duration": duration,
        "billsec": billsec,
    }


def _send_webhook(payload: dict) -> None:
    headers = {"Content-Type": "application/json"}
    if WEBHOOK_TOKEN:
        headers["X-Telephony-Token"] = WEBHOOK_TOKEN
    try:
        resp = requests.post(
            WEBHOOK_URL, json=payload, headers=headers, timeout=WEBHOOK_TIMEOUT
        )
        resp.raise_for_status()
        logger.info(
            "Webhook sent for %s → %s (status %d)",
            payload.get("source_number"),
            payload.get("destination_number"),
            resp.status_code,
        )
    except requests.RequestException:
        logger.exception("Webhook delivery failed for call %s", payload.get("call_id"))


def run():
    logger.info(
        "Starting AMI CDR listener (host=%s, port=%d, user=%s)",
        AMI_HOST, AMI_PORT, AMI_USER,
    )
    while True:
        try:
            sock = _ami_connect()
            buf = ""
            sock.settimeout(60)
            while True:
                try:
                    data = sock.recv(4096)
                except socket.timeout:
                    # Send keepalive ping
                    sock.sendall(b"Action: Ping\r\n\r\n")
                    continue
                if not data:
                    raise ConnectionError("AMI connection closed")
                buf += data.decode("utf-8", errors="replace")
                events, buf = _parse_events(buf)
                for event in events:
                    if event.get("Event") != "Cdr":
                        continue
                    payload = _build_webhook_payload(event)
                    if payload:
                        _send_webhook(payload)
        except Exception:
            logger.exception("AMI connection error — reconnecting in %ds", RECONNECT_DELAY)
            time.sleep(RECONNECT_DELAY)
