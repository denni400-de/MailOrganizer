"""Application-wide constants."""

APP_NAME = "MailOrganizer"
APP_DATA_DIR = "~/.mailorganizer"
LOG_DIR = f"{APP_DATA_DIR}/logs"
LOG_FILE = f"{LOG_DIR}/app.log"

DEFAULT_DATABASE_PATH = f"{APP_DATA_DIR}/data.db"

DEFAULT_IMAP_PORT = 993
DEFAULT_SMTP_PORT = 587

DEFAULT_OLLAMA_URL = "http://localhost:11434"
DEFAULT_OLLAMA_MODEL = "mistral:latest"
DEFAULT_OLLAMA_TEMPERATURE = 0.7
DEFAULT_OLLAMA_MAX_TOKENS = 500

DEFAULT_AUTO_SYNC_INTERVAL = 300  # seconds

CATEGORIES = ["work", "personal", "bills", "news", "shopping", "spam", "other"]

RECOMMENDED_ACTIONS = ["archive", "flag", "delete", "reply", "read_later"]

SENTIMENTS = ["positive", "neutral", "negative"]

IMPORTANCE_MIN = 1
IMPORTANCE_MAX = 5

ANALYSIS_SYSTEM_PROMPT = """Du bist ein professioneller Mail-Analyst. Analysiere die folgende E-Mail \
und liefere eine strukturierte Analyse.

Antworte IMMER in diesem exakten JSON-Format:
{
    "category": "work|personal|bills|news|shopping|spam|other",
    "importance_score": 1-5,
    "sentiment": "positive|neutral|negative",
    "summary": "Kurze 1-2 Satz Zusammenfassung",
    "recommended_action": "archive|flag|delete|reply|read_later",
    "keywords": ["keyword1", "keyword2"],
    "reasoning": "Kurze Erklärung der Entscheidungen"
}"""

ANALYSIS_USER_PROMPT_TEMPLATE = """Analysiere diese E-Mail:

Von: {sender}
Betreff: {subject}
Datum: {date}
---
{body_excerpt}

Beachte:
- Dies ist E-Mail #{email_number} von {sender}
- User Sprache: {user_language}
- Benutzer-Kontext: {user_preferences}"""
