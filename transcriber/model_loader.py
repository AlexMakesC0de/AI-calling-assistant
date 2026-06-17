"""Resilient model fetching for poor / intermittent network connections.

The transcriber depends on two large model downloads from the Hugging Face
Hub: the faster-whisper CTranslate2 weights (selected by ``WHISPER_MODEL_SIZE``)
and the SpeechBrain ECAPA speaker encoder. By default both are fetched lazily
the first time the model object is constructed, in a single attempt with no
retry. On a slow or flaky link that single attempt fails and the gunicorn
worker crashes on import, so the whole service never becomes healthy.

This module wraps the download in an exponential-backoff retry loop. Two
properties make the retries cheap and safe:

  * ``huggingface_hub`` writes partial blobs to ``*.incomplete`` files and
    resumes them on the next call, so a retry continues an interrupted
    download rather than starting from zero.
  * ``snapshot_download`` is idempotent — once every file is present it
    returns immediately, so calling it on an already-cached model is a no-op.

We deliberately retry only *transport* failures (network/HTTP). A malformed
repo id or an auth error is not transient, so we surface it on the first
occurrence instead of wasting the full backoff budget.
"""

from __future__ import annotations

import logging
import time
from typing import Callable, TypeVar

from huggingface_hub import snapshot_download

logger = logging.getLogger(__name__)

# Failures that will never succeed on retry — fail fast instead of backing off.
# Resolved by name so a missing/renamed symbol in a future huggingface_hub
# release degrades to "retry everything" rather than crashing the import (which
# would take down the whole worker). The names below are stable across the
# pinned >=0.21,<1.0 range.
_NON_RETRYABLE: tuple[type[BaseException], ...]
try:
    from huggingface_hub.utils import (
        EntryNotFoundError,
        GatedRepoError,
        RepositoryNotFoundError,
        RevisionNotFoundError,
    )

    _NON_RETRYABLE = (
        RepositoryNotFoundError,
        RevisionNotFoundError,
        EntryNotFoundError,
        GatedRepoError,
    )
except ImportError:  # pragma: no cover — defensive against HF API drift
    logger.warning(
        "huggingface_hub error types unavailable; treating all download "
        "failures as retryable."
    )
    _NON_RETRYABLE = ()

# Faster-whisper resolves bare size aliases (e.g. "large-v2") to these repos.
# We mirror that mapping so we can pre-fetch the snapshot ourselves with retry
# before handing the local path to WhisperModel.
_WHISPER_REPO_BY_SIZE = {
    "tiny": "Systran/faster-whisper-tiny",
    "tiny.en": "Systran/faster-whisper-tiny.en",
    "base": "Systran/faster-whisper-base",
    "base.en": "Systran/faster-whisper-base.en",
    "small": "Systran/faster-whisper-small",
    "small.en": "Systran/faster-whisper-small.en",
    "medium": "Systran/faster-whisper-medium",
    "medium.en": "Systran/faster-whisper-medium.en",
    "large-v1": "Systran/faster-whisper-large-v1",
    "large-v2": "Systran/faster-whisper-large-v2",
    "large-v3": "Systran/faster-whisper-large-v3",
}

T = TypeVar("T")


def _retry_with_backoff(
    operation: Callable[[], T],
    *,
    description: str,
    max_attempts: int,
    base_delay_seconds: float,
    max_delay_seconds: float,
) -> T:
    """Run ``operation`` until it succeeds or the attempt budget is exhausted.

    Backoff doubles each attempt, capped at ``max_delay_seconds``. Only
    transient errors are retried; non-retryable errors propagate immediately.
    The final failed attempt re-raises the original exception so the caller
    sees the real cause.
    """
    last_error: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            return operation()
        except _NON_RETRYABLE:
            # Configuration error, not a network blip — no point retrying.
            raise
        except Exception as error:  # noqa: BLE001 — transport errors are broad
            last_error = error
            if attempt == max_attempts:
                break
            delay = min(base_delay_seconds * (2 ** (attempt - 1)), max_delay_seconds)
            logger.warning(
                "%s failed (attempt %d/%d): %s — retrying in %.1fs",
                description,
                attempt,
                max_attempts,
                error,
                delay,
            )
            time.sleep(delay)

    raise RuntimeError(
        f"{description} failed after {max_attempts} attempts"
    ) from last_error


def download_whisper_snapshot(
    model_size_or_repo: str,
    *,
    max_attempts: int,
    base_delay_seconds: float,
    max_delay_seconds: float,
) -> str:
    """Fetch the faster-whisper snapshot with resumable retries.

    Returns a local directory path suitable for passing to ``WhisperModel``.
    Resuming relies on huggingface_hub's ``*.incomplete`` blob handling, so an
    interrupted download continues rather than restarting.

    A local path or an explicit ``org/repo`` id is downloaded as-is; a bare
    size alias (e.g. ``"large-v2"``) is mapped to its canonical Systran repo.
    """
    repo_id = _WHISPER_REPO_BY_SIZE.get(model_size_or_repo, model_size_or_repo)

    logger.info("Ensuring Whisper model '%s' is cached locally...", repo_id)
    local_path = _retry_with_backoff(
        lambda: snapshot_download(repo_id=repo_id),
        description=f"Whisper model download ({repo_id})",
        max_attempts=max_attempts,
        base_delay_seconds=base_delay_seconds,
        max_delay_seconds=max_delay_seconds,
    )
    logger.info("Whisper model '%s' available at %s", repo_id, local_path)
    return local_path


def run_with_download_retry(
    operation: Callable[[], T],
    *,
    description: str,
    max_attempts: int,
    base_delay_seconds: float,
    max_delay_seconds: float,
) -> T:
    """Retry an arbitrary model-loading callable that downloads on first use.

    Used for loaders we do not pre-fetch ourselves (e.g. SpeechBrain's
    ``from_hparams``), giving them the same backoff behaviour. The callable
    must be idempotent so that a retry after a partial download is safe — the
    SpeechBrain and HF loaders are, because they resume cached files.
    """
    return _retry_with_backoff(
        operation,
        description=description,
        max_attempts=max_attempts,
        base_delay_seconds=base_delay_seconds,
        max_delay_seconds=max_delay_seconds,
    )
