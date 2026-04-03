"""Build diarized/plain text and API segment lists from word dicts."""

# ---------------------------------------------------------------------------
# Core logic – Transcript formatting
# ---------------------------------------------------------------------------


def build_diarized_transcript(words: list[dict]) -> str:
    """Build a readable transcript with speaker labels.

    Output format:
        Speaker 1: Hello, how can I help you today?
        Speaker 2: Hi, I have a problem with my account.
    """
    if not words:
        return ""

    lines = []
    current_speaker = None
    current_text = []

    for word in words:
        speaker = word.get("speaker", 1)
        if speaker != current_speaker:
            # Save previous line
            if current_text:
                lines.append(
                    f"Speaker {current_speaker}: {''.join(current_text).strip()}"
                )
            current_speaker = speaker
            current_text = [word["word"]]
        else:
            current_text.append(word["word"])

    # Don't forget the last line
    if current_text:
        lines.append(f"Speaker {current_speaker}: {''.join(current_text).strip()}")

    return "\n".join(lines)


def build_plain_transcript(words: list[dict]) -> str:
    """Build a plain transcript without speaker labels (fallback)."""
    return " ".join(w["word"] for w in words).strip()


def build_segments(words: list[dict]) -> list[dict]:
    """Group consecutive words by speaker into segments."""
    if not words:
        return []

    segments = []
    current = {
        "speaker": words[0].get("speaker", 1),
        "text_parts": [words[0]["word"]],
        "start": words[0]["start"],
        "end": words[0]["end"],
    }

    for word in words[1:]:
        if word.get("speaker", 1) == current["speaker"]:
            current["text_parts"].append(word["word"])
            current["end"] = word["end"]
        else:
            segments.append({
                "speaker": current["speaker"],
                "text": "".join(current["text_parts"]).strip(),
                "start": round(current["start"], 2),
                "end": round(current["end"], 2),
            })
            current = {
                "speaker": word.get("speaker", 1),
                "text_parts": [word["word"]],
                "start": word["start"],
                "end": word["end"],
            }

    segments.append({
        "speaker": current["speaker"],
        "text": "".join(current["text_parts"]).strip(),
        "start": round(current["start"], 2),
        "end": round(current["end"], 2),
    })

    return segments
