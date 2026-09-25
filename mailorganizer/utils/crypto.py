"""Symmetric encryption helpers for storing credentials (IMAP/SMTP passwords)."""

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

from mailorganizer.utils.exceptions import CredentialError


def generate_master_key() -> str:
    """Generate a new Fernet master key, to be stored as MAILORGANIZER_MASTER_KEY."""
    return Fernet.generate_key().decode("utf-8")


def encrypt_password(plain_password: str, master_key: str) -> str:
    """Encrypt a plaintext password with the given master key."""
    if not master_key:
        raise CredentialError("No master key configured; cannot encrypt password")
    try:
        fernet = Fernet(master_key.encode("utf-8"))
        return fernet.encrypt(plain_password.encode("utf-8")).decode("utf-8")
    except (ValueError, TypeError) as exc:
        raise CredentialError(f"Failed to encrypt password: {exc}") from exc


def decrypt_password(encrypted_password: str, master_key: str) -> str:
    """Decrypt a password previously encrypted with encrypt_password."""
    if not master_key:
        raise CredentialError("No master key configured; cannot decrypt password")
    try:
        fernet = Fernet(master_key.encode("utf-8"))
        return fernet.decrypt(encrypted_password.encode("utf-8")).decode("utf-8")
    except (InvalidToken, ValueError, TypeError) as exc:
        raise CredentialError(f"Failed to decrypt password: {exc}") from exc
