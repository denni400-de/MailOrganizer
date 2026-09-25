from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests

from mailorganizer.services.webhook_service import WebhookConfig, WebhookError, WebhookService, _build_payload


def make_mail(sender="s@x.com", subject="Subject"):
    mail = MagicMock()
    mail.id = 1
    mail.sender = sender
    mail.subject = subject
    return mail


def make_analysis(importance_score=4, category="work"):
    analysis = MagicMock()
    analysis.importance_score = importance_score
    analysis.category = category
    analysis.sentiment = "neutral"
    analysis.summary = "summary"
    analysis.recommended_action = "flag"
    return analysis


def test_should_notify_respects_threshold():
    config = WebhookConfig(url="https://example.com/hook", importance_threshold=4)
    service = WebhookService(config)
    assert service.should_notify(make_analysis(importance_score=4)) is True
    assert service.should_notify(make_analysis(importance_score=3)) is False


def test_should_notify_false_when_disabled():
    config = WebhookConfig(url="https://example.com/hook", enabled=False)
    service = WebhookService(config)
    assert service.should_notify(make_analysis(importance_score=5)) is False


def test_should_notify_false_without_url():
    config = WebhookConfig(url="", importance_threshold=1)
    service = WebhookService(config)
    assert service.should_notify(make_analysis(importance_score=5)) is False


def test_build_payload_slack_format():
    payload = _build_payload(make_mail(), make_analysis(), "slack")
    assert "text" in payload
    assert "s@x.com" in payload["text"]


def test_build_payload_discord_format():
    payload = _build_payload(make_mail(), make_analysis(), "discord")
    assert "content" in payload


def test_build_payload_generic_format():
    payload = _build_payload(make_mail(), make_analysis(), "generic")
    assert payload["category"] == "work"
    assert payload["importance_score"] == 4


@patch("mailorganizer.services.webhook_service.requests.post")
def test_notify_if_important_sends_when_threshold_met(mock_post):
    mock_post.return_value = MagicMock(ok=True, raise_for_status=MagicMock())
    config = WebhookConfig(url="https://example.com/hook", importance_threshold=3)
    service = WebhookService(config)

    sent = service.notify_if_important(make_mail(), make_analysis(importance_score=4))

    assert sent is True
    mock_post.assert_called_once()


@patch("mailorganizer.services.webhook_service.requests.post")
def test_notify_if_important_skips_below_threshold(mock_post):
    config = WebhookConfig(url="https://example.com/hook", importance_threshold=5)
    service = WebhookService(config)

    sent = service.notify_if_important(make_mail(), make_analysis(importance_score=2))

    assert sent is False
    mock_post.assert_not_called()


@patch("mailorganizer.services.webhook_service.requests.post")
def test_notify_raises_webhook_error_on_failure(mock_post):
    mock_post.side_effect = requests.RequestException("boom")
    config = WebhookConfig(url="https://example.com/hook")
    service = WebhookService(config)

    with pytest.raises(WebhookError):
        service.notify(make_mail(), make_analysis())
