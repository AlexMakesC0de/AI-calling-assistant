"""Speaker embeddings and spectral clustering for diarization."""

import logging

import numpy as np
import soundfile as sf
import torch
from scipy.signal import resample_poly
from sklearn.cluster import SpectralClustering

from models import speaker_model

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Core logic – Diarization (audio + speaker clustering)
# ---------------------------------------------------------------------------


def load_audio(audio_path: str) -> tuple[torch.Tensor, int]:
    """Load audio file and resample to 16kHz mono."""
    audio, sample_rate = sf.read(audio_path, always_2d=False)

    if isinstance(audio, np.ndarray) and audio.ndim > 1:
        audio = np.mean(audio, axis=1)

    if sample_rate != 16000:
        audio = resample_poly(audio, 16000, sample_rate)
        sample_rate = 16000

    waveform = torch.tensor(audio, dtype=torch.float32).unsqueeze(0)
    return waveform, sample_rate


def _get_speaker_embedding(
    waveform: torch.Tensor,
    sample_rate: int,
    start: float,
    end: float,
) -> np.ndarray | None:
    """Extract a speaker embedding for a time range from the audio.

    Returns None if the segment is too short (< 0.3s).
    """
    start_sample = int(start * sample_rate)
    end_sample = int(end * sample_rate)

    # Need at least 0.3 seconds for a reliable embedding
    if (end_sample - start_sample) < int(0.3 * sample_rate):
        return None

    segment = waveform[:, start_sample:end_sample]
    if segment.shape[1] == 0:
        return None

    with torch.no_grad():
        embedding = speaker_model.encode_batch(segment)
    return embedding.squeeze().cpu().numpy()


def assign_speakers(
    words: list[dict],
    waveform: torch.Tensor,
    sample_rate: int,
    num_speakers: int,
) -> list[dict]:
    """Assign a speaker label to each word using speaker embeddings
    and spectral clustering.

    Groups consecutive words into chunks (~2-3 seconds each) to get
    reliable speaker embeddings, then clusters the embeddings.
    """
    if not words:
        return words

    # Group words into chunks for more reliable embeddings
    chunks = []
    current_chunk = {"words": [], "start": words[0]["start"], "end": words[0]["end"]}

    for i, word in enumerate(words):
        current_chunk["words"].append(word)
        current_chunk["end"] = word["end"]

        # Create a new chunk every ~2.5 seconds or on long pauses
        chunk_duration = current_chunk["end"] - current_chunk["start"]
        next_idx = i + 1
        gap = (words[next_idx]["start"] - word["end"]) if next_idx < len(words) else 999

        if chunk_duration >= 2.5 or gap > 1.0:
            chunks.append(current_chunk)
            if next_idx < len(words):
                current_chunk = {
                    "words": [],
                    "start": words[next_idx]["start"],
                    "end": words[next_idx]["start"],
                }
            else:
                current_chunk = {"words": [], "start": 0, "end": 0}

    # Don't forget the last chunk
    if current_chunk["words"]:
        chunks.append(current_chunk)

    logger.info("Created %d chunks for speaker embedding", len(chunks))

    # Extract embeddings for each chunk
    embeddings = []
    valid_chunks = []
    for chunk in chunks:
        emb = _get_speaker_embedding(
            waveform, sample_rate, chunk["start"], chunk["end"]
        )
        if emb is not None:
            embeddings.append(emb)
            valid_chunks.append(chunk)

    if len(embeddings) < 2:
        # Not enough data to cluster — assign all to Speaker 1
        logger.warning(
            "Not enough chunks for clustering (%d). Assigning all to Speaker 1.",
            len(embeddings),
        )
        for word in words:
            word["speaker"] = 1
        return words

    # Cluster embeddings
    embedding_matrix = np.array(embeddings)
    n_clusters = min(num_speakers, len(embeddings))

    try:
        clustering = SpectralClustering(
            n_clusters=n_clusters,
            affinity="cosine",
            random_state=42,
        )
        labels = clustering.fit_predict(embedding_matrix)
    except Exception as exc:
        logger.warning(
            "Spectral clustering failed, falling back to simple assignment: %s",
            exc,
        )
        # Fallback: alternate speakers on pauses
        for word in words:
            word["speaker"] = 1
        return words

    # Assign speaker labels to each word based on its chunk
    for chunk, label in zip(valid_chunks, labels):
        for word in chunk["words"]:
            word["speaker"] = int(label) + 1  # 1-indexed

    # Fill in any words without a speaker (from invalid chunks)
    last_speaker = 1
    for word in words:
        if "speaker" not in word:
            word["speaker"] = last_speaker
        else:
            last_speaker = word["speaker"]

    return words
