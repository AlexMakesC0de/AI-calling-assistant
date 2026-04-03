def safe_stem(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in value)
    return cleaned[:120] if cleaned else "event"
