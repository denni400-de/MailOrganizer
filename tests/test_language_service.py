from __future__ import annotations

from mailorganizer.services.language_service import detect_language


def test_detect_german():
    text = "Hallo, ich bitte um eine schnelle Antwort. Vielen Dank und viele Grüße."
    assert detect_language(text) == "Deutsch"


def test_detect_english():
    text = "Hello, please review this and thank you very much. Best regards."
    assert detect_language(text) == "English"


def test_detect_french():
    text = "Bonjour, merci pour votre message. Cordialement, nous vous remercions."
    assert detect_language(text) == "Français"


def test_empty_text_returns_default():
    assert detect_language("") == "Deutsch"
    assert detect_language("   ") == "Deutsch"


def test_no_stopword_overlap_returns_default():
    assert detect_language("xyzxyz qwqwq 12345") == "Deutsch"


def test_custom_default():
    assert detect_language("", default="English") == "English"
