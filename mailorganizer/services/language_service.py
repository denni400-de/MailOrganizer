"""Lightweight stopword-based language detection (plan section 8.6), deliberately
dependency-free per plan section 16 ("Dependencies Minimieren").
"""

from __future__ import annotations

import re

_WORD_RE = re.compile(r"[a-zA-ZäöüÄÖÜß]+")

# A short list of very common, highly language-specific stopwords is enough to
# distinguish German/English/French/Spanish for short mail bodies without a model.
_STOPWORDS: dict[str, set[str]] = {
    "Deutsch": {
        "der", "die", "das", "und", "ist", "ich", "nicht", "mit", "sie", "auf",
        "für", "sich", "des", "dem", "den", "ein", "eine", "wir", "sind", "bitte",
        "vielen", "dank", "gruß", "grüße", "mfg", "heute", "morgen",
    },
    "English": {
        "the", "and", "is", "are", "you", "your", "for", "with", "this", "that",
        "please", "thanks", "thank", "regards", "best", "have", "will", "from",
        "hello", "hi",
    },
    "Français": {
        "le", "la", "les", "et", "est", "vous", "pour", "avec", "bonjour",
        "merci", "cordialement", "nous", "votre",
    },
    "Español": {
        "el", "la", "los", "las", "y", "es", "usted", "para", "con", "hola",
        "gracias", "saludos", "nosotros",
    },
}

DEFAULT_LANGUAGE = "Deutsch"


def detect_language(text: str, default: str = DEFAULT_LANGUAGE) -> str:
    """Guess the language of `text` from stopword overlap. Falls back to `default`."""
    if not text or not text.strip():
        return default

    words = {w.lower() for w in _WORD_RE.findall(text)}
    if not words:
        return default

    scores = {lang: len(words & stopwords) for lang, stopwords in _STOPWORDS.items()}
    best_lang, best_score = max(scores.items(), key=lambda kv: kv[1])
    if best_score == 0:
        return default
    return best_lang
