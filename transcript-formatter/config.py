"""
Configuration and environment variables for the Transcript Formatter service.
"""

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# Ollama Configuration
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
OLLAMA_CONNECT_TIMEOUT = float(os.getenv("OLLAMA_CONNECT_TIMEOUT", "3"))
OLLAMA_READ_TIMEOUT = float(os.getenv("OLLAMA_READ_TIMEOUT", "120"))
OLLAMA_TRANSLATE_READ_TIMEOUT = float(
    os.getenv("OLLAMA_TRANSLATE_READ_TIMEOUT", str(max(OLLAMA_READ_TIMEOUT, 120.0)))
)
OLLAMA_PULL_TIMEOUT = float(os.getenv("OLLAMA_PULL_TIMEOUT", "900"))

# Translation Configuration
TRANSLATION_TIME_BUDGET = float(os.getenv("TRANSLATION_TIME_BUDGET", "240"))
TRANSLATION_CHUNK_MAX_CHARS = int(os.getenv("TRANSLATION_CHUNK_MAX_CHARS", "2500"))
DEFAULT_INCLUDE_DUTCH_TRANSLATION = os.getenv(
    "DEFAULT_INCLUDE_DUTCH_TRANSLATION", "true"
).strip().lower() in ("1", "true", "yes", "on")

# Content Filtering Configuration
TERM_FILTER_MODE = os.getenv("TERM_FILTER_MODE", "basic").strip().lower()
TERM_FILTER_CUSTOM_WORDS = os.getenv("TERM_FILTER_CUSTOM_WORDS", "")
TERM_FILTER_REPLACEMENT = os.getenv("TERM_FILTER_REPLACEMENT", "[redacted]")

# Flask Configuration
TEMPLATE_DIR = os.getenv("TEMPLATE_DIR", "/data/shared/templates")

# Basic profanity filter terms (used in "basic" filter mode)
BASIC_FILTER_TERMS = {
    "nigger",
    "nigga",
    "faggot",
    "retard",
    "whore",
    "slut",
}

# Regex patterns for transcript processing
NON_ACTION_STEP_PATTERNS = [
    r"^\s*(hi|hello|hey|good\s+(morning|afternoon|evening))\b",
    r"\bmy name is\b",
    r"\bthis is\b",
    r"\bi am\b",
    r"\bi'm\b",
    r"\bcan you help me\b",
    r"\bplease help\b",
    r"\bi need help\b",
]

ACTION_HINT_PATTERNS = [
    r"\b(check(ed)?|verify|verified|diagnos(ed|is)|troubleshoot(ed|ing)?)\b",
    r"\b(reset|restart(ed)?|reboot(ed)?|reinstall(ed)?|configur(ed|ing))\b",
    r"\b(ask(ed)?|instruct(ed|ion)|advis(ed|e)|guid(ed|ance)|walk(ed)?\s+through)\b",
    r"\b(escalat(ed|e)|open(ed)?\s+(a\s+)?(ticket|case)|creat(ed)?\s+(a\s+)?(ticket|case))\b",
    r"\b(test(ed|ing)?|collect(ed)?|updat(ed|ing)?|provid(ed|ing)?)\b",
]

# Fields that have confidence scores
SCORED_FIELDS = [
    "caller_name", "account_or_reference", "contact_info", "agent_name",
    "issue_category", "issue_priority", "issue_description", "error_messages",
    "resolution_status", "steps_taken", "resolution_outcome",
    "follow_up_required", "follow_up_actions", "follow_up_department",
    "customer_sentiment", "call_summary",
]

# AI Prompt Template
# The extraction prompt is stored in prompts/extraction.txt so it can be
# edited and reloaded with a service restart, without rebuilding the image.
# The placeholder {TRANSCRIPT} is substituted at request time via str.replace.
PROMPT_TEMPLATE_PATH = Path(
    os.getenv(
        "FORM_FILL_PROMPT_PATH",
        str(Path(__file__).resolve().parent / "prompts" / "extraction.txt"),
    )
)


def _load_form_fill_prompt() -> str:
    try:
        return PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        logger.error(
            "Prompt template missing at %s; LLM extraction will fail until restored.",
            PROMPT_TEMPLATE_PATH,
        )
        return ""


FORM_FILL_PROMPT_TEMPLATE = _load_form_fill_prompt()
