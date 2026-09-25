"""Lightweight dataclasses representing a mail fetched from IMAP, decoupled from the ORM."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class MailData:
    """A parsed mail message, ready for storage or analysis."""

    message_id: str
    sender: str
    recipients: list[str]
    subject: str
    received_at: datetime
    cc: list[str] = field(default_factory=list)
    body: str = ""
    html_body: str = ""
    is_read: bool = False
    is_archived: bool = False
    is_important: bool = False
    is_spam: bool = False
    uid: int | None = None
    folder: str = "INBOX"

    def body_excerpt(self, max_chars: int = 2000) -> str:
        text = self.body or self.html_body
        return text[:max_chars]
