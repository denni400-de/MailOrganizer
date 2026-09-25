from __future__ import annotations

from email.message import EmailMessage
from unittest.mock import MagicMock, patch

import pytest
from imapclient.exceptions import IMAPClientError

from mailorganizer.services.mail_service import MailAccountCredentials, MailService
from mailorganizer.utils.exceptions import MailConnectionError, MailFetchError, MailSendError, ValidationError


def make_credentials(**overrides) -> MailAccountCredentials:
    defaults = dict(
        email_address="user@example.com",
        password="secret",
        imap_server="imap.example.com",
        imap_port=993,
        smtp_server="smtp.example.com",
        smtp_port=587,
    )
    defaults.update(overrides)
    return MailAccountCredentials(**defaults)


def test_credentials_validate_rejects_invalid_email():
    creds = make_credentials(email_address="not-an-email")
    with pytest.raises(ValidationError):
        creds.validate()


def test_credentials_validate_accepts_valid_data():
    creds = make_credentials()
    creds.validate()  # should not raise


@patch("mailorganizer.services.mail_service.IMAPClient")
def test_connect_success(mock_imap_cls):
    mock_client = MagicMock()
    mock_imap_cls.return_value = mock_client

    service = MailService(make_credentials())
    service.connect()

    mock_client.login.assert_called_once_with("user@example.com", "secret")
    assert service._imap is mock_client


@patch("mailorganizer.services.mail_service.IMAPClient")
def test_connect_failure_raises_mail_connection_error(mock_imap_cls):
    mock_client = MagicMock()
    mock_client.login.side_effect = IMAPClientError("bad login")
    mock_imap_cls.return_value = mock_client

    service = MailService(make_credentials())
    with pytest.raises(MailConnectionError):
        service.connect()


def test_fetch_mails_without_connection_raises():
    service = MailService(make_credentials())
    with pytest.raises(MailConnectionError):
        service.fetch_mails()


def _build_raw_message() -> bytes:
    msg = EmailMessage()
    msg["From"] = "Sender Name <sender@example.com>"
    msg["To"] = "user@example.com"
    msg["Subject"] = "Test Subject"
    msg["Date"] = "Mon, 01 Jan 2024 10:00:00 +0000"
    msg.set_content("Hello world")
    return bytes(msg)


@patch("mailorganizer.services.mail_service.IMAPClient")
def test_fetch_mails_parses_messages(mock_imap_cls):
    mock_client = MagicMock()
    mock_imap_cls.return_value = mock_client
    mock_client.search.return_value = [1]
    raw = _build_raw_message()
    mock_client.fetch.return_value = {1: {b"RFC822": raw, b"FLAGS": (b"\\Seen",)}}

    service = MailService(make_credentials())
    service.connect()
    mails = service.fetch_mails(limit=10)

    assert len(mails) == 1
    mail = mails[0]
    assert mail.sender == "sender@example.com"
    assert mail.subject == "Test Subject"
    assert mail.body.strip() == "Hello world"
    assert mail.is_read is True


@patch("mailorganizer.services.mail_service.IMAPClient")
def test_fetch_mails_wraps_errors(mock_imap_cls):
    mock_client = MagicMock()
    mock_imap_cls.return_value = mock_client
    mock_client.search.side_effect = IMAPClientError("boom")

    service = MailService(make_credentials())
    service.connect()
    with pytest.raises(MailFetchError):
        service.fetch_mails()


def test_send_mail_without_smtp_server_raises():
    service = MailService(make_credentials(smtp_server=""))
    with pytest.raises(MailSendError):
        service.send_mail(["to@example.com"], "Subject", "Body")


@patch("mailorganizer.services.mail_service.smtplib.SMTP")
def test_send_mail_success(mock_smtp_cls):
    mock_smtp = MagicMock()
    mock_smtp_cls.return_value.__enter__.return_value = mock_smtp

    service = MailService(make_credentials())
    service.send_mail(["to@example.com"], "Subject", "Body")

    mock_smtp.starttls.assert_called_once()
    mock_smtp.login.assert_called_once()
    mock_smtp.send_message.assert_called_once()
