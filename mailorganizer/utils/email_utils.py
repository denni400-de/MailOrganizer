"""Helper functions for parsing and manipulating email content."""

from __future__ import annotations

import re
from email.header import decode_header
from email.utils import parseaddr, parsedate_to_datetime
from datetime import datetime

_WHITESPACE_RE = re.compile(r"\s+")
_HTML_TAG_RE = re.compile(r"<[^>]+>")


def decode_mime_header(value: str | None) -> str:
    """Decode a raw MIME header (e.g. Subject) into a plain unicode string."""
    if not value:
        return ""
    parts = decode_header(value)
    decoded = []
    for text, encoding in parts:
        if isinstance(text, bytes):
            decoded.append(text.decode(encoding or "utf-8", errors="replace"))
        else:
            decoded.append(text)
    return "".join(decoded)


def extract_email_address(from_header: str | None) -> str:
    """Extract the bare email address from a From/To header value."""
    if not from_header:
        return ""
    _, address = parseaddr(from_header)
    return address


def parse_email_date(date_header: str | None) -> datetime | None:
    """Parse an RFC 2822 date header into a datetime, or None if unparsable."""
    if not date_header:
        return None
    try:
        return parsedate_to_datetime(date_header)
    except (TypeError, ValueError):
        return None


def strip_html(html: str | None) -> str:
    """Strip HTML tags from a string, collapsing whitespace."""
    if not html:
        return ""
    text = _HTML_TAG_RE.sub(" ", html)
    return _WHITESPACE_RE.sub(" ", text).strip()


def truncate_body(body: str | None, max_chars: int = 2000) -> str:
    """Truncate a mail body to a maximum number of characters for LLM prompts."""
    if not body:
        return ""
    body = body.strip()
    if len(body) <= max_chars:
        return body
    return body[:max_chars].rsplit(" ", 1)[0] + "..."
