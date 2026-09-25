"""IMAP/SMTP operations: connecting, fetching, sending, flagging and moving mails."""

from __future__ import annotations

import smtplib
from dataclasses import dataclass
from datetime import datetime
from email.message import EmailMessage
from email.parser import BytesParser
from email.policy import default as default_policy

from imapclient import IMAPClient
from imapclient.exceptions import IMAPClientError

from mailorganizer.models.mail import MailData
from mailorganizer.utils.email_utils import (
    decode_mime_header,
    extract_email_address,
    parse_email_date,
)
from mailorganizer.utils.exceptions import MailConnectionError, MailFetchError, MailSendError
from mailorganizer.utils.logger import get_logger
from mailorganizer.utils.validators import validate_email_address, validate_hostname, validate_port

logger = get_logger("mail_service")


@dataclass
class MailAccountCredentials:
    """Connection details for a single mail account."""

    email_address: str
    password: str
    imap_server: str
    imap_port: int = 993
    smtp_server: str = ""
    smtp_port: int = 587

    def validate(self) -> None:
        validate_email_address(self.email_address)
        validate_hostname(self.imap_server)
        validate_port(self.imap_port)
        if self.smtp_server:
            validate_hostname(self.smtp_server)
            validate_port(self.smtp_port)


class MailService:
    """Handles IMAP fetching/flagging and SMTP sending for one mail account."""

    def __init__(self, credentials: MailAccountCredentials):
        credentials.validate()
        self.credentials = credentials
        self._imap: IMAPClient | None = None

    # -- IMAP connection -------------------------------------------------

    def connect(self) -> None:
        """Open and authenticate an IMAP connection."""
        try:
            self._imap = IMAPClient(self.credentials.imap_server, port=self.credentials.imap_port, use_uid=True, ssl=True)
            self._imap.login(self.credentials.email_address, self.credentials.password)
            logger.info("IMAP connected for %s", self.credentials.email_address)
        except (IMAPClientError, OSError) as exc:
            logger.error("IMAP connection failed: %s", exc)
            raise MailConnectionError(f"IMAP connection failed: {exc}") from exc

    def disconnect(self) -> None:
        """Close the IMAP connection if open."""
        if self._imap is not None:
            try:
                self._imap.logout()
            except (IMAPClientError, OSError):
                pass
            finally:
                self._imap = None

    def __enter__(self) -> "MailService":
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.disconnect()

    def _require_connection(self) -> IMAPClient:
        if self._imap is None:
            raise MailConnectionError("Not connected. Call connect() first.")
        return self._imap

    # -- Fetching ----------------------------------------------------------

    def fetch_mails(self, folder: str = "INBOX", limit: int = 50, unseen_only: bool = False) -> list[MailData]:
        """Fetch up to `limit` most recent mails from the given folder."""
        imap = self._require_connection()
        try:
            imap.select_folder(folder, readonly=True)
            criteria = ["UNSEEN"] if unseen_only else ["ALL"]
            uids = imap.search(criteria)
            uids = sorted(uids)[-limit:] if limit else sorted(uids)
            if not uids:
                return []

            response = imap.fetch(uids, ["RFC822", "FLAGS"])
            mails: list[MailData] = []
            for uid, data in response.items():
                raw = data.get(b"RFC822")
                if raw is None:
                    continue
                flags = data.get(b"FLAGS", ())
                mails.append(self._parse_message(raw, uid, folder, flags))
            mails.sort(key=lambda m: m.received_at)
            return mails
        except (IMAPClientError, OSError) as exc:
            logger.error("Fetching mails failed: %s", exc)
            raise MailFetchError(f"Fetching mails failed: {exc}") from exc

    @staticmethod
    def _parse_message(raw: bytes, uid: int, folder: str, flags: tuple) -> MailData:
        msg = BytesParser(policy=default_policy).parsebytes(raw)

        body = ""
        html_body = ""
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                disposition = part.get_content_disposition()
                if disposition == "attachment":
                    continue
                if content_type == "text/plain" and not body:
                    body = part.get_content()
                elif content_type == "text/html" and not html_body:
                    html_body = part.get_content()
        else:
            if msg.get_content_type() == "text/html":
                html_body = msg.get_content()
            else:
                body = msg.get_content()

        recipients = [extract_email_address(addr) for addr in (msg.get_all("To") or [])]
        cc = [extract_email_address(addr) for addr in (msg.get_all("Cc") or [])]
        received_at = parse_email_date(msg.get("Date"))

        return MailData(
            message_id=msg.get("Message-ID", f"<generated-{uid}@mailorganizer>"),
            sender=extract_email_address(msg.get("From")),
            recipients=[r for r in recipients if r],
            cc=[c for c in cc if c],
            subject=decode_mime_header(msg.get("Subject")),
            body=body,
            html_body=html_body,
            received_at=received_at or datetime.now(),
            is_read=b"\\Seen" in flags,
            is_important=b"\\Flagged" in flags,
            uid=uid,
            folder=folder,
        )

    # -- Mutations -----------------------------------------------------

    def mark_flag(self, uid: int, flag: str, folder: str = "INBOX", add: bool = True) -> None:
        """Add or remove an IMAP flag (e.g. \\Seen, \\Flagged, \\Deleted) on a message."""
        imap = self._require_connection()
        try:
            imap.select_folder(folder)
            if add:
                imap.add_flags([uid], [flag])
            else:
                imap.remove_flags([uid], [flag])
        except (IMAPClientError, OSError) as exc:
            raise MailFetchError(f"Failed to update flag {flag} on uid {uid}: {exc}") from exc

    def move_mail(self, uid: int, destination_folder: str, source_folder: str = "INBOX") -> None:
        """Move a message to another folder (e.g. Archive)."""
        imap = self._require_connection()
        try:
            imap.select_folder(source_folder)
            imap.move([uid], destination_folder)
            logger.info("Moved mail uid=%s to %s", uid, destination_folder)
        except (IMAPClientError, OSError) as exc:
            raise MailFetchError(f"Failed to move mail uid={uid}: {exc}") from exc

    def delete_mail(self, uid: int, folder: str = "INBOX") -> None:
        """Mark a message as deleted and expunge it."""
        imap = self._require_connection()
        try:
            imap.select_folder(folder)
            imap.add_flags([uid], [b"\\Deleted"])
            imap.expunge()
            logger.info("Deleted mail uid=%s", uid)
        except (IMAPClientError, OSError) as exc:
            raise MailFetchError(f"Failed to delete mail uid={uid}: {exc}") from exc

    # -- Sending ---------------------------------------------------------

    def send_mail(self, to: list[str], subject: str, body: str, cc: list[str] | None = None) -> None:
        """Send a plain-text email via SMTP with STARTTLS."""
        if not self.credentials.smtp_server:
            raise MailSendError("No SMTP server configured")

        msg = EmailMessage()
        msg["From"] = self.credentials.email_address
        msg["To"] = ", ".join(to)
        if cc:
            msg["Cc"] = ", ".join(cc)
        msg["Subject"] = subject
        msg.set_content(body)

        try:
            with smtplib.SMTP(self.credentials.smtp_server, self.credentials.smtp_port, timeout=30) as smtp:
                smtp.starttls()
                smtp.login(self.credentials.email_address, self.credentials.password)
                smtp.send_message(msg, to_addrs=list(to) + list(cc or []))
            logger.info("Mail sent to %s", to)
        except (smtplib.SMTPException, OSError) as exc:
            logger.error("Sending mail failed: %s", exc)
            raise MailSendError(f"Sending mail failed: {exc}") from exc
