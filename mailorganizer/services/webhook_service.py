"""External-service integrations (plan section 8.5): Slack/Discord notifications and
generic webhooks fired when an important mail is analyzed.
"""

from __future__ import annotations

from dataclasses import dataclass

import requests

from mailorganizer.models.database import Mail, MailAnalysis
from mailorganizer.utils.exceptions import MailOrganizerError
from mailorganizer.utils.logger import get_logger

logger = get_logger("webhook_service")

WEBHOOK_FORMATS = ["generic", "slack", "discord"]

DEFAULT_TIMEOUT = 10


class WebhookError(MailOrganizerError):
    """Raised when sending a webhook notification fails."""


@dataclass
class WebhookConfig:
    """Persisted (via Settings key/value) webhook notification configuration."""

    url: str
    format: str = "generic"
    enabled: bool = True
    importance_threshold: int = 4


def _build_payload(mail: Mail, analysis: MailAnalysis, fmt: str) -> dict:
    text = (
        f"Wichtige Mail von {mail.sender}: \"{mail.subject}\"\n"
        f"Kategorie: {analysis.category} | Wichtigkeit: {analysis.importance_score}/5\n"
        f"{analysis.summary or ''}"
    )
    if fmt == "slack":
        return {"text": text}
    if fmt == "discord":
        return {"content": text}
    # generic: full structured payload for custom automation (n8n, Zapier, etc.)
    return {
        "sender": mail.sender,
        "subject": mail.subject,
        "category": analysis.category,
        "importance_score": analysis.importance_score,
        "sentiment": analysis.sentiment,
        "summary": analysis.summary,
        "recommended_action": analysis.recommended_action,
    }


class WebhookService:
    """Sends notifications for important mails to a configured Slack/Discord/generic webhook."""

    def __init__(self, config: WebhookConfig, timeout: int = DEFAULT_TIMEOUT):
        self.config = config
        self.timeout = timeout

    def should_notify(self, analysis: MailAnalysis) -> bool:
        if not self.config.enabled or not self.config.url:
            return False
        return (analysis.importance_score or 0) >= self.config.importance_threshold

    def notify(self, mail: Mail, analysis: MailAnalysis) -> None:
        """Send a webhook notification for `mail`, raising WebhookError on failure."""
        payload = _build_payload(mail, analysis, self.config.format)
        try:
            response = requests.post(self.config.url, json=payload, timeout=self.timeout)
            response.raise_for_status()
            logger.info("Webhook notification sent for mail %s", mail.id)
        except requests.RequestException as exc:
            logger.error("Webhook notification failed: %s", exc)
            raise WebhookError(f"Webhook notification failed: {exc}") from exc

    def notify_if_important(self, mail: Mail, analysis: MailAnalysis) -> bool:
        """Send a notification if the mail meets the importance threshold. Returns True if sent."""
        if not self.should_notify(analysis):
            return False
        self.notify(mail, analysis)
        return True
