"""Input validation helpers."""

from __future__ import annotations

import re

from mailorganizer.utils.exceptions import ValidationError

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validate_email_address(address: str) -> str:
    """Validate an email address, returning it stripped or raising ValidationError."""
    address = (address or "").strip()
    if not address or not _EMAIL_RE.match(address):
        raise ValidationError(f"Invalid email address: {address!r}")
    return address


def validate_port(port: int) -> int:
    """Validate a TCP port number."""
    if not isinstance(port, int) or not (0 < port <= 65535):
        raise ValidationError(f"Invalid port number: {port!r}")
    return port


def validate_hostname(hostname: str) -> str:
    """Validate a server hostname is non-empty and reasonably well-formed."""
    hostname = (hostname or "").strip()
    if not hostname or len(hostname) > 255 or " " in hostname:
        raise ValidationError(f"Invalid hostname: {hostname!r}")
    return hostname


def validate_non_empty(value: str, field_name: str, max_length: int | None = None) -> str:
    """Validate a string field is non-empty and optionally within a max length."""
    value = (value or "").strip()
    if not value:
        raise ValidationError(f"{field_name} must not be empty")
    if max_length is not None and len(value) > max_length:
        raise ValidationError(f"{field_name} exceeds max length of {max_length}")
    return value


def validate_importance_score(score: int) -> int:
    """Validate an importance score is within the allowed 1-5 range."""
    from mailorganizer.config import constants

    if not isinstance(score, int) or not (constants.IMPORTANCE_MIN <= score <= constants.IMPORTANCE_MAX):
        raise ValidationError(
            f"Importance score must be between {constants.IMPORTANCE_MIN} and {constants.IMPORTANCE_MAX}"
        )
    return score
