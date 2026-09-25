"""Database persistence for users, mails, analysis results and settings."""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, joinedload, sessionmaker

from mailorganizer.models.analysis import AnalysisResult
from mailorganizer.models.database import Mail, MailAnalysis, OllamaConfig, Setting, User, create_all, init_engine
from mailorganizer.models.mail import MailData
from mailorganizer.utils.exceptions import StorageError
from mailorganizer.utils.logger import get_logger

logger = get_logger("storage_service")


class StorageService:
    """Query interface for all persisted MailOrganizer data."""

    def __init__(self, database_path: str | Path, echo: bool = False):
        self.engine = init_engine(database_path, echo=echo)
        create_all(self.engine)
        self._session_factory: sessionmaker = sessionmaker(bind=self.engine, expire_on_commit=False)

    def session(self) -> Session:
        return self._session_factory()

    # -- Users -------------------------------------------------------------

    def get_or_create_user(
        self,
        email_address: str,
        imap_server: str,
        smtp_server: str,
        password_encrypted: str,
        imap_port: int = 993,
        smtp_port: int = 587,
    ) -> User:
        with self.session() as session:
            try:
                user = session.scalar(select(User).where(User.email_address == email_address))
                if user is None:
                    user = User(
                        email_address=email_address,
                        imap_server=imap_server,
                        imap_port=imap_port,
                        smtp_server=smtp_server,
                        smtp_port=smtp_port,
                        password_encrypted=password_encrypted,
                    )
                    session.add(user)
                else:
                    user.imap_server = imap_server
                    user.imap_port = imap_port
                    user.smtp_server = smtp_server
                    user.smtp_port = smtp_port
                    user.password_encrypted = password_encrypted
                session.commit()
                session.refresh(user)
                return user
            except SQLAlchemyError as exc:
                session.rollback()
                raise StorageError(f"Failed to save user: {exc}") from exc

    # -- Mails ---------------------------------------------------------

    def save_mail(self, user_id: int, mail: MailData) -> Mail:
        """Insert a mail if it doesn't already exist (by message_id), else return the existing row."""
        with self.session() as session:
            try:
                existing = session.scalar(select(Mail).where(Mail.message_id == mail.message_id))
                if existing is not None:
                    return existing

                row = Mail(
                    message_id=mail.message_id,
                    user_id=user_id,
                    sender=mail.sender,
                    recipients=json.dumps(mail.recipients),
                    cc=json.dumps(mail.cc),
                    subject=mail.subject,
                    body=mail.body,
                    html_body=mail.html_body,
                    received_at=mail.received_at,
                    is_read=mail.is_read,
                    is_archived=mail.is_archived,
                    is_important=mail.is_important,
                    is_spam=mail.is_spam,
                )
                session.add(row)
                session.commit()
                session.refresh(row)
                return row
            except SQLAlchemyError as exc:
                session.rollback()
                raise StorageError(f"Failed to save mail {mail.message_id}: {exc}") from exc

    def list_mails(
        self,
        user_id: int,
        include_archived: bool = False,
        include_spam: bool = False,
        limit: int = 100,
    ) -> list[Mail]:
        with self.session() as session:
            try:
                stmt = select(Mail).options(joinedload(Mail.analysis)).where(Mail.user_id == user_id)
                if not include_archived:
                    stmt = stmt.where(Mail.is_archived.is_(False))
                if not include_spam:
                    stmt = stmt.where(Mail.is_spam.is_(False))
                stmt = stmt.order_by(Mail.received_at.desc()).limit(limit)
                return list(session.scalars(stmt))
            except SQLAlchemyError as exc:
                raise StorageError(f"Failed to list mails: {exc}") from exc

    def set_mail_flags(
        self,
        mail_id: int,
        is_read: bool | None = None,
        is_archived: bool | None = None,
        is_important: bool | None = None,
        is_spam: bool | None = None,
    ) -> None:
        with self.session() as session:
            try:
                mail = session.get(Mail, mail_id)
                if mail is None:
                    raise StorageError(f"Mail {mail_id} not found")
                if is_read is not None:
                    mail.is_read = is_read
                if is_archived is not None:
                    mail.is_archived = is_archived
                if is_important is not None:
                    mail.is_important = is_important
                if is_spam is not None:
                    mail.is_spam = is_spam
                session.commit()
            except SQLAlchemyError as exc:
                session.rollback()
                raise StorageError(f"Failed to update flags for mail {mail_id}: {exc}") from exc

    # -- Analysis --------------------------------------------------------

    def save_analysis(self, mail_id: int, result: AnalysisResult) -> MailAnalysis:
        with self.session() as session:
            try:
                existing = session.scalar(select(MailAnalysis).where(MailAnalysis.mail_id == mail_id))
                if existing is None:
                    existing = MailAnalysis(mail_id=mail_id)
                    session.add(existing)

                existing.category = result.category
                existing.importance_score = result.importance_score
                existing.sentiment = result.sentiment
                existing.summary = result.summary
                existing.recommended_action = result.recommended_action
                existing.keywords = json.dumps(result.keywords)
                existing.ollama_model = result.ollama_model
                existing.processing_time_ms = result.processing_time_ms

                session.commit()
                session.refresh(existing)
                return existing
            except SQLAlchemyError as exc:
                session.rollback()
                raise StorageError(f"Failed to save analysis for mail {mail_id}: {exc}") from exc

    # -- Settings --------------------------------------------------------

    def get_setting(self, user_id: int, key: str, default: str | None = None) -> str | None:
        with self.session() as session:
            row = session.scalar(select(Setting).where(Setting.user_id == user_id, Setting.key == key))
            return row.value if row else default

    def set_setting(self, user_id: int, key: str, value: str) -> None:
        with self.session() as session:
            try:
                row = session.scalar(select(Setting).where(Setting.user_id == user_id, Setting.key == key))
                if row is None:
                    row = Setting(user_id=user_id, key=key, value=value)
                    session.add(row)
                else:
                    row.value = value
                session.commit()
            except SQLAlchemyError as exc:
                session.rollback()
                raise StorageError(f"Failed to save setting {key}: {exc}") from exc

    # -- Ollama config -----------------------------------------------------

    def get_ollama_config(self, user_id: int) -> OllamaConfig | None:
        with self.session() as session:
            return session.scalar(select(OllamaConfig).where(OllamaConfig.user_id == user_id))

    def save_ollama_config(
        self,
        user_id: int,
        ollama_url: str,
        ollama_model: str,
        temperature: float = 0.7,
        max_tokens: int = 500,
    ) -> OllamaConfig:
        with self.session() as session:
            try:
                config = session.scalar(select(OllamaConfig).where(OllamaConfig.user_id == user_id))
                if config is None:
                    config = OllamaConfig(user_id=user_id)
                    session.add(config)
                config.ollama_url = ollama_url
                config.ollama_model = ollama_model
                config.temperature = temperature
                config.max_tokens = max_tokens
                session.commit()
                session.refresh(config)
                return config
            except SQLAlchemyError as exc:
                session.rollback()
                raise StorageError(f"Failed to save Ollama config: {exc}") from exc
