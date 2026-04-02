import os
from dataclasses import dataclass
from pathlib import Path


DEFAULT_ALLOWED_EXTENSIONS = {"wav", "mp3", "ogg", "flac", "m4a", "webm"}
DEFAULT_ALLOWED_MIME_TYPES = {
    "audio/wav",
    "audio/x-wav",
    "audio/wave",
    "audio/mpeg",
    "audio/mp3",
    "audio/ogg",
    "audio/flac",
    "audio/mp4",
    "audio/m4a",
    "audio/x-m4a",
    "audio/webm",
    "video/webm",
}


@dataclass(frozen=True)
class AppConfig:
    upload_dir: Path
    whisper_url: str
    formatter_url: str
    formatter_timeout_seconds: int
    email_url: str
    support_email: str
    max_file_size_mb: int
    allowed_extensions: frozenset[str]
    allowed_mime_types: frozenset[str]

    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str
    db_save_wait_seconds: int

    storage_account_email: str
    storage_account_password: str

    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_mb * 1024 * 1024

    @classmethod
    def from_env(cls) -> "AppConfig":
        upload_dir = Path(os.getenv("UPLOAD_DIR", "/data/shared/uploads"))
        try:
            upload_dir.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            fallback_upload_dir = Path(
                os.getenv("UPLOAD_DIR_FALLBACK", "/tmp/uploads")
            )
            fallback_upload_dir.mkdir(parents=True, exist_ok=True)
            upload_dir = fallback_upload_dir

        whisper_url = os.getenv(
            "TRANSCRIBER_URL",
            os.getenv("WHISPER_URL", "http://localhost:9000/transcribe"),
        )

        return cls(
            upload_dir=upload_dir,
            whisper_url=whisper_url,
            formatter_url=os.getenv("FORMATTER_URL", "http://localhost:5001/format"),
            formatter_timeout_seconds=max(
                120, int(os.getenv("FORMATTER_TIMEOUT_SECONDS", "360"))
            ),
            email_url=os.getenv("EMAIL_URL", "http://email-sender:5002/send"),
            support_email=os.getenv("SUPPORT_EMAIL", "support-team@example.com"),
            max_file_size_mb=int(os.getenv("MAX_FILE_SIZE_MB", "50")),
            allowed_extensions=frozenset(DEFAULT_ALLOWED_EXTENSIONS),
            allowed_mime_types=frozenset(DEFAULT_ALLOWED_MIME_TYPES),
            db_host=os.getenv("DB_HOST", "localhost"),
            db_port=int(os.getenv("DB_PORT", "5432")),
            db_name=os.getenv("DB_NAME", os.getenv("POSTGRES_DB", "support_db")),
            db_user=os.getenv("DB_USER", os.getenv("POSTGRES_USER", "support")),
            db_password=os.getenv(
                "DB_PASSWORD", os.getenv("POSTGRES_PASSWORD", "support_secret")
            ),
            db_save_wait_seconds=max(
                5, min(10, int(os.getenv("DB_SAVE_WAIT_SECONDS", "8")))
            ),
            storage_account_email=os.getenv(
                "STORAGE_ACCOUNT_EMAIL", "voice-app-storage@local"
            ),
            storage_account_password=os.getenv(
                "STORAGE_ACCOUNT_PASSWORD", "not-for-login"
            ),
        )