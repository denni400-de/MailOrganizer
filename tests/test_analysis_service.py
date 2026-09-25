from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from mailorganizer.models.mail import MailData
from mailorganizer.services.analysis_service import AnalysisService
from mailorganizer.services.ollama_service import OllamaResponse
from mailorganizer.utils.exceptions import AnalysisError


def make_mail() -> MailData:
    return MailData(
        message_id="<1@example.com>",
        sender="boss@example.com",
        recipients=["user@example.com"],
        subject="Quarterly Report",
        received_at=datetime(2024, 1, 1, 10, 0, 0),
        body="Please review the attached report before Friday.",
    )


def test_build_prompt_contains_key_fields():
    service = AnalysisService(ollama_service=MagicMock(), model="mistral:latest")
    prompt = service.build_prompt(make_mail())

    assert "boss@example.com" in prompt
    assert "Quarterly Report" in prompt
    assert "Please review" in prompt


def test_parse_response_valid_json():
    raw = """Here is my analysis:
    {
        "category": "work",
        "importance_score": 4,
        "sentiment": "positive",
        "summary": "Report review request.",
        "recommended_action": "flag",
        "keywords": ["report", "deadline"],
        "reasoning": "Work related with a deadline."
    }
    """
    result = AnalysisService.parse_response(raw)

    assert result.category == "work"
    assert result.importance_score == 4
    assert result.sentiment == "positive"
    assert result.recommended_action == "flag"
    assert result.keywords == ["report", "deadline"]


def test_parse_response_invalid_category_falls_back_to_other():
    raw = '{"category": "unknown_cat", "importance_score": 3, "sentiment": "neutral", "summary": "s", "recommended_action": "archive"}'
    result = AnalysisService.parse_response(raw)
    assert result.category == "other"


def test_parse_response_clamps_importance_score():
    raw = '{"category": "work", "importance_score": 99, "sentiment": "neutral", "summary": "s", "recommended_action": "archive"}'
    result = AnalysisService.parse_response(raw)
    assert result.importance_score == 5


def test_parse_response_no_json_raises():
    with pytest.raises(AnalysisError):
        AnalysisService.parse_response("no json here at all")


def test_analyze_mail_success():
    ollama = MagicMock()
    ollama.generate.return_value = OllamaResponse(
        text='{"category": "work", "importance_score": 5, "sentiment": "positive", '
        '"summary": "Important", "recommended_action": "reply", "keywords": ["x"]}',
        model="mistral:latest",
    )
    service = AnalysisService(ollama_service=ollama, model="mistral:latest")

    result = service.analyze_mail(make_mail())

    assert result.category == "work"
    assert result.ollama_model == "mistral:latest"
    assert result.processing_time_ms is not None


def test_analyze_mail_wraps_ollama_errors():
    ollama = MagicMock()
    ollama.generate.side_effect = RuntimeError("connection lost")
    service = AnalysisService(ollama_service=ollama, model="mistral:latest")

    with pytest.raises(AnalysisError):
        service.analyze_mail(make_mail())
