import logging
import os
import threading
import time

logger = logging.getLogger(__name__)


_RETRY_ATTEMPTS = int(os.getenv("WORD_LIST_RETRY_ATTEMPTS", "9"))
_RETRY_BASE_DELAY = float(os.getenv("WORD_LIST_RETRY_BASE_DELAY", "1.0"))
_RETRY_MAX_DELAY = float(os.getenv("WORD_LIST_RETRY_MAX_DELAY", "30.0"))

_LOAD_TIMEOUT = float(os.getenv("WORD_LIST_LOAD_TIMEOUT", "150.0"))


class _SetProxy:
    """Frozenset-like proxy populated asynchronously; callers block until ready."""

    __slots__ = ("_name", "_data", "_ready", "_failed")

    def __init__(self, name: str) -> None:
        self._name = name
        self._data: frozenset = frozenset()
        self._ready = threading.Event()
        self._failed = False

    def _populate(self, data: frozenset) -> None:
        self._data = data
        self._ready.set()

    def _mark_failed(self) -> None:
        self._failed = True
        self._ready.set()

    def _await(self) -> None:
        if not self._ready.wait(timeout=_LOAD_TIMEOUT):
            raise RuntimeError(
                f"word_lists: {self._name} load timed out after {_LOAD_TIMEOUT:.0f}s"
            )
        if self._failed:
            raise RuntimeError(
                f"word_lists: {self._name} unavailable — PostgreSQL load failed "
                f"after {_RETRY_ATTEMPTS} attempts"
            )

    def __contains__(self, item: object) -> bool:
        self._await()
        return item in self._data

    def __iter__(self):
        self._await()
        return iter(self._data)

    def __len__(self) -> int:
        self._await()
        return len(self._data)

    def __bool__(self) -> bool:
        self._await()
        return bool(self._data)


FIRST_NAMES: _SetProxy = _SetProxy("FIRST_NAMES")
TUSSENVOEGSELS: _SetProxy = _SetProxy("TUSSENVOEGSELS")
PROFANITY_TERMS: _SetProxy = _SetProxy("PROFANITY_TERMS")


def _load_from_db() -> tuple[frozenset, frozenset, frozenset]:
    import psycopg2

    conn = psycopg2.connect(
        host=os.getenv("DB_HOST", "database"),
        port=int(os.getenv("DB_PORT", "5432")),
        dbname=os.getenv("DB_NAME", "support_db"),
        user=os.getenv("DB_USER", "support"),
        password=os.getenv("DB_PASSWORD", "support_secret"),
        connect_timeout=5,
    )
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT value, category FROM name_dictionary")
            rows = cur.fetchall()
            cur.execute("SELECT json_agg(term) FROM profanity_terms")
            profanity_json = cur.fetchone()[0]
    finally:
        conn.close()

    first_names: set[str] = set()
    tussenvoegsels: set[str] = set()
    for value, category in rows:
        if category == "first_name":
            first_names.add(value.lower())
        elif category == "tussenvoegsel":
            tussenvoegsels.add(value.lower())

    profanity = {t.lower() for t in (profanity_json or [])}

    if not first_names or not profanity:
        raise ValueError(
            f"name_dictionary or profanity_terms table is empty "
            f"({len(first_names)} names, {len(profanity)} profanity terms)"
        )

    return frozenset(first_names), frozenset(tussenvoegsels), frozenset(profanity)


def _loader() -> None:
    delay = _RETRY_BASE_DELAY
    waited_total = 0.0
    for attempt in range(1, _RETRY_ATTEMPTS + 1):
        try:
            first_names, tussenvoegsels, profanity = _load_from_db()
        except Exception as exc:
            is_last = attempt == _RETRY_ATTEMPTS
            logger.warning(
                "word_lists: attempt %d/%d failed (%s)%s",
                attempt,
                _RETRY_ATTEMPTS,
                exc,
                "" if is_last else f" — retrying in {delay:.0f}s",
            )
            if not is_last:
                time.sleep(delay)
                waited_total += delay
                delay = min(delay * 2, _RETRY_MAX_DELAY)
            continue

        FIRST_NAMES._populate(first_names)
        TUSSENVOEGSELS._populate(tussenvoegsels)
        PROFANITY_TERMS._populate(profanity)
        logger.info(
            "word_lists: loaded %d first names, %d tussenvoegsels, %d profanity terms",
            len(first_names),
            len(tussenvoegsels),
            len(profanity),
        )
        return

    logger.critical(
        "word_lists: all %d attempts over ~%.0fs exhausted — name validation and "
        "profanity filtering are DOWN. Verify the '%s' database is reachable and "
        "seeded; tune WORD_LIST_RETRY_ATTEMPTS / WORD_LIST_RETRY_MAX_DELAY if the "
        "DB legitimately starts slower than this budget.",
        _RETRY_ATTEMPTS,
        waited_total,
        os.getenv("DB_HOST", "database"),
    )
    FIRST_NAMES._mark_failed()
    TUSSENVOEGSELS._mark_failed()
    PROFANITY_TERMS._mark_failed()


threading.Thread(target=_loader, name="word-lists-loader", daemon=True).start()


def word_lists_ready() -> bool:
    return FIRST_NAMES._ready.is_set() and not FIRST_NAMES._failed


def normalize_name(text: str) -> str:
    """Title-case a name, keeping Dutch tussenvoegsels lowercase mid-name.

    Examples:
        "jan van den berg" -> "Jan van den Berg"
        "emma de vries"    -> "Emma de Vries"
        "anna"             -> "Anna"
    """
    words = text.strip().split()
    result = []
    for i, word in enumerate(words):
        if i > 0 and word.lower() in TUSSENVOEGSELS:
            result.append(word.lower())
        else:
            result.append(word.capitalize())
    return " ".join(result)


def name_in_db(text: str) -> bool:
    """Return True if the text contains at least one known first name."""
    words = text.strip().lower().split()
    return any(w in FIRST_NAMES for w in words)
