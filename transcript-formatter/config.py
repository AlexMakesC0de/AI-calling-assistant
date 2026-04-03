"""
Configuration and environment variables for the Transcript Formatter service.
"""

import os

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
FORM_FILL_PROMPT_TEMPLATE = """\
You are an experienced customer-support analyst. You have just received a \
transcript of a support call. The transcript uses speaker diarization — each \
line is prefixed with a speaker label such as "Speaker 1:" or "Speaker 2:". \
In most calls, the person who speaks first is the support agent (they greet \
the caller), and the other speaker is the customer/caller. Use these labels \
to accurately identify who said what.

The transcript may be in English, Dutch, or another language. If needed, \
translate internally while extracting data, but keep the final JSON values in \
clear English (except proper names, product names, and exact error text).

Your job is to read through the conversation \
and fill out the incident form below by extracting the relevant information \
from the transcript.

Fill out EVERY field as accurately as possible based on what was said in the \
call. If information for a field was not mentioned, write "Not mentioned" for \
string fields or use your best judgement for enum fields.

For each field, also rate your CONFIDENCE as "high", "medium", or "low":
- "high" = the information was explicitly stated in the transcript
- "medium" = you inferred it from context
- "low" = it was not mentioned and you are guessing

Return ONLY a valid JSON object with EXACTLY these keys (no markdown fences, \
no extra text, no explanation):

{{
  "caller_name": "<caller's name or 'Not mentioned'>",
  "caller_name_confidence": "<high|medium|low>",
  "account_or_reference": "<any account/customer ID/reference number or 'Not mentioned'>",
  "account_or_reference_confidence": "<high|medium|low>",
  "contact_info": "<phone or email if mentioned, or 'Not mentioned'>",
  "contact_info_confidence": "<high|medium|low>",
  "agent_name": "<support agent's name or 'Not mentioned'>",
  "agent_name_confidence": "<high|medium|low>",
  "issue_category": "<one of: Technical, Billing, Account, Shipping, Network, Software, Hardware, General>",
  "issue_category_confidence": "<high|medium|low>",
  "issue_priority": "<one of: Low, Medium, High, Critical>",
  "issue_priority_confidence": "<high|medium|low>",
  "issue_description": "<clear description of the caller's problem>",
  "issue_description_confidence": "<high|medium|low>",
  "error_messages": "<any specific error messages/codes mentioned or 'None'>",
  "error_messages_confidence": "<high|medium|low>",
  "resolution_status": "<one of: Resolved, Partially Resolved, Unresolved, Escalated>",
  "resolution_status_confidence": "<high|medium|low>",
  "steps_taken": ["<step 1>", "<step 2>"],
  "steps_taken_confidence": "<high|medium|low>",
  "resolution_outcome": "<what was the final result of the call>",
  "resolution_outcome_confidence": "<high|medium|low>",
  "follow_up_required": true or false,
  "follow_up_required_confidence": "<high|medium|low>",
  "follow_up_actions": ["<action 1>"] or [],
  "follow_up_actions_confidence": "<high|medium|low>",
  "follow_up_department": "<department to escalate to, or 'None'>",
  "follow_up_department_confidence": "<high|medium|low>",
  "customer_sentiment": "<one of: Very Satisfied, Satisfied, Neutral, Dissatisfied, Very Dissatisfied>",
  "customer_sentiment_confidence": "<high|medium|low>",
  "call_summary": "<2-3 sentence summary of the entire call>",
  "call_summary_confidence": "<high|medium|low>"
}}

TRANSCRIPT:
{transcript}
"""
