import logging
import os

logger = logging.getLogger(__name__)


def _load() -> tuple[frozenset[str], frozenset[str], frozenset[str]]:
    import psycopg2

    try:
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
    except Exception as exc:
        logger.error("word_lists: failed to load from PostgreSQL (%s) — name validation and profanity filter disabled", exc)
        return frozenset(), frozenset(), frozenset()

    first_names: set[str] = set()
    tussenvoegels: set[str] = set()
    for value, category in rows:
        if category == "first_name":
            first_names.add(value.lower())
        elif category == "tussenvoegel":
            tussenvoegels.add(value.lower())

    profanity = {t.lower() for t in (profanity_json or [])}

    logger.info(
        "word_lists: loaded %d first names, %d tussenvoegels, %d profanity terms",
        len(first_names), len(tussenvoegels), len(profanity),
    )
    return frozenset(first_names), frozenset(tussenvoegels), frozenset(profanity)


FIRST_NAMES, TUSSENVOEGELS, PROFANITY_TERMS = _load()


# ── Public helpers ────────────────────────────────────────────────────────────

def normalize_name(text: str) -> str:
    """Title-case a name, keeping Dutch tussenvoegels lowercase mid-name.

    Examples:
        "jan van den berg" -> "Jan van den Berg"
        "emma de vries"    -> "Emma de Vries"
        "anna"             -> "Anna"
    """
    words = text.strip().split()
    result = []
    for i, word in enumerate(words):
        if i > 0 and word.lower() in TUSSENVOEGELS:
            result.append(word.lower())
        else:
            result.append(word.capitalize())
    return " ".join(result)


def name_in_db(text: str) -> bool:
    """Return True if the text contains at least one known first name."""
    words = text.strip().lower().split()
    return any(w in FIRST_NAMES for w in words)
