import logging
from pathlib import Path
from typing import Any

import requests
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from config import AppConfig


_RETRYABLE = (requests.exceptions.ConnectionError, requests.exceptions.Timeout)


class PipelineClients:
    def __init__(self, config: AppConfig, log: logging.Logger):
        self._config = config
        self._log = log

    @retry(
        retry=retry_if_exception_type(_RETRYABLE),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=30),
        before_sleep=before_sleep_log(logging.getLogger(__name__), logging.WARNING),
        reraise=True,
    )
    def transcribe(self, filepath: Path) -> dict[str, Any]:
        with open(filepath, "rb") as f:
            if self._config.whisper_url.rstrip("/").endswith("/asr"):
                files = {"audio_file": (filepath.name, f, "audio/wav")}
                params = {"task": "transcribe", "output": "json"}
                resp = requests.post(
                    self._config.whisper_url,
                    files=files,
                    params=params,
                    timeout=300,
                )
            else:
                files = {"file": (filepath.name, f, "audio/wav")}
                resp = requests.post(self._config.whisper_url, files=files, timeout=300)
        resp.raise_for_status()
        return resp.json()

    @retry(
        retry=retry_if_exception_type(_RETRYABLE),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=30),
        before_sleep=before_sleep_log(logging.getLogger(__name__), logging.WARNING),
        reraise=True,
    )
    def call_formatter(
        self, transcript_text: str, metadata: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        resp = requests.post(
            self._config.formatter_url,
            json={"transcript": transcript_text, "metadata": metadata or {}},
            timeout=180,
        )
        resp.raise_for_status()
        return resp.json()

    @retry(
        retry=retry_if_exception_type(_RETRYABLE),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=30),
        before_sleep=before_sleep_log(logging.getLogger(__name__), logging.WARNING),
        reraise=True,
    )
    def send_email(self, payload: dict[str, Any]) -> dict[str, Any]:
        resp = requests.post(self._config.email_url, json=payload, timeout=30)
        resp.raise_for_status()
        return resp.json()