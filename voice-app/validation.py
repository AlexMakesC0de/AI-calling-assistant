import magic

from config import AppConfig


class UploadValidator:
    def __init__(self, config: AppConfig):
        self._config = config

    def validate(self, file) -> tuple[bool, str]:
        """Validate an uploaded file for extension, size, and MIME type."""
        filename = file.filename or ""

        if "." not in filename:
            return False, "File has no extension."
        ext = filename.rsplit(".", 1)[1].lower()
        if ext not in self._config.allowed_extensions:
            return (
                False,
                f"Extension '.{ext}' not allowed. Accepted: {sorted(self._config.allowed_extensions)}",
            )

        file.seek(0, 2)
        size = file.tell()
        file.seek(0)
        if size > self._config.max_file_size_bytes:
            return (
                False,
                f"File too large ({size / 1024 / 1024:.1f} MB). Maximum: {self._config.max_file_size_mb} MB.",
            )
        if size == 0:
            return False, "File is empty (0 bytes)."

        header = file.read(8192)
        file.seek(0)
        detected_mime = magic.from_buffer(header, mime=True)
        if detected_mime not in self._config.allowed_mime_types:
            return (
                False,
                f"Invalid audio file. Detected type: '{detected_mime}'. Expected audio format.",
            )

        return True, ""