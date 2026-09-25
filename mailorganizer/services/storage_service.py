"""Database persistence for users, mails, analysis results and settings."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, joinedload, sessionmaker

from mailorganizer.models.analysis import AnalysisResult
from mailorganizer.models.database import (
    AnalysisRule,
    Mail,
    MailAnalysis,
    OllamaConfig,
    Setting,
    User,
    create_all,
    init_engine,
)
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
                existing = session.scalar(
                    select(Mail).options(joinedload(Mail.analysis)).where(Mail.message_id == mail.message_id)
                )
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
                _ = row.analysis  # load the relationship (always None for a new row) before the session closes
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

    def hard_delete_mail(self, mail_id: int) -> None:
        """Permanently remove a mail row (and its analysis, via cascade) from the database."""
        with self.session() as session:
            try:
                mail = session.get(Mail, mail_id)
                if mail is None:
                    return
                session.delete(mail)
                session.commit()
            except SQLAlchemyError as exc:
                session.rollback()
                raise StorageError(f"Failed to delete mail {mail_id}: {exc}") from exc

    def list_mails_for_cleanup(self, user_id: int) -> list[Mail]:
        """Return all mails for a user (including archived/spam), with analysis eager-loaded."""
        with self.session() as session:
            try:
                stmt = select(Mail).options(joinedload(Mail.analysis)).where(Mail.user_id == user_id)
                stmt = stmt.order_by(Mail.received_at.desc())
                return list(session.scalars(stmt))
            except SQLAlchemyError as exc:
                raise StorageError(f"Failed to list mails for cleanup: {exc}") from exc

    def archive_mails_older_than(self, user_id: int, days: int) -> int:
        """Mark all non-archived mails older than `days` as archived. Returns the count affected."""
        cutoff = datetime.now() - timedelta(days=days)
        with self.session() as session:
            try:
                stmt = select(Mail).where(
                    Mail.user_id == user_id,
                    Mail.is_archived.is_(False),
                    Mail.received_at < cutoff,
                )
                mails = list(session.scalars(stmt))
                for mail in mails:
                    mail.is_archived = True
                session.commit()
                return len(mails)
            except SQLAlchemyError as exc:
                session.rollback()
                raise StorageError(f"Failed to archive old mails: {exc}") from exc

    def archive_mails_by_sender(self, user_id: int, sender: str) -> int:
        """Mark all non-archived mails from `sender` as archived. Returns the count affected."""
        with self.session() as session:
            try:
                stmt = select(Mail).where(
                    Mail.user_id == user_id,
                    Mail.sender == sender,
                    Mail.is_archived.is_(False),
                )
                mails = list(session.scalars(stmt))
                for mail in mails:
                    mail.is_archived = True
                session.commit()
                return len(mails)
            except SQLAlchemyError as exc:
                session.rollback()
                raise StorageError(f"Failed to archive mails from {sender}: {exc}") from exc

    def delete_spam_mails(self, user_id: int) -> int:
        """Permanently delete all mails flagged as spam. Returns the count deleted."""
        with self.session() as session:
            try:
                stmt = select(Mail).where(Mail.user_id == user_id, Mail.is_spam.is_(True))
                mails = list(session.scalars(stmt))
                for mail in mails:
                    session.delete(mail)
                session.commit()
                return len(mails)
            except SQLAlchemyError as exc:
                session.rollback()
                raise StorageError(f"Failed to delete spam mails: {exc}") from exc

    def delete_duplicate_mails(self, user_id: int) -> int:
        """Delete duplicate mails (same sender+subject+received_at), keeping the newest by id.

        Returns the count deleted.
        """
        with self.session() as session:
            try:
                stmt = select(Mail).where(Mail.user_id == user_id).order_by(Mail.id.desc())
                mails = list(session.scalars(stmt))
                seen: set[tuple[str, str, datetime]] = set()
                duplicates: list[Mail] = []
                for mail in mails:
                    key = (mail.sender, mail.subject, mail.received_at)
                    if key in seen:
                        duplicates.append(mail)
                    else:
                        seen.add(key)
                for mail in duplicates:
                    session.delete(mail)
                session.commit()
                return len(duplicates)
            except SQLAlchemyError as exc:
                session.rollback()
                raise StorageError(f"Failed to delete duplicate mails: {exc}") from exc

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

    # -- Analysis rules ----------------------------------------------------

    def list_rules(self, user_id: int, active_only: bool = False) -> list[AnalysisRule]:
        with self.session() as session:
            try:
                stmt = select(AnalysisRule).where(AnalysisRule.user_id == user_id)
                if active_only:
                    stmt = stmt.where(AnalysisRule.is_active.is_(True))
                stmt = stmt.order_by(AnalysisRule.priority.asc(), AnalysisRule.id.asc())
                return list(session.scalars(stmt))
            except SQLAlchemyError as exc:
                raise StorageError(f"Failed to list rules: {exc}") from exc

    def create_rule(
        self,
        user_id: int,
        name: str,
        condition: str,
        action: str,
        priority: int = 1,
        is_active: bool = True,
    ) -> AnalysisRule:
        with self.session() as session:
            try:
                rule = AnalysisRule(
                    user_id=user_id,
                    name=name,
                    condition=condition,
                    action=action,
                    priority=priority,
                    is_active=is_active,
                )
                session.add(rule)
                session.commit()
                session.refresh(rule)
                return rule
            except SQLAlchemyError as exc:
                session.rollback()
                raise StorageError(f"Failed to create rule: {exc}") from exc

    def update_rule(
        self,
        rule_id: int,
        name: str | None = None,
        condition: str | None = None,
        action: str | None = None,
        priority: int | None = None,
        is_active: bool | None = None,
    ) -> AnalysisRule:
        with self.session() as session:
            try:
                rule = session.get(AnalysisRule, rule_id)
                if rule is None:
                    raise StorageError(f"Rule {rule_id} not found")
                if name is not None:
                    rule.name = name
                if condition is not None:
                    rule.condition = condition
                if action is not None:
                    rule.action = action
                if priority is not None:
                    rule.priority = priority
                if is_active is not None:
                    rule.is_active = is_active
                session.commit()
                session.refresh(rule)
                return rule
            except SQLAlchemyError as exc:
                session.rollback()
                raise StorageError(f"Failed to update rule {rule_id}: {exc}") from exc

    def delete_rule(self, rule_id: int) -> None:
        with self.session() as session:
            try:
                rule = session.get(AnalysisRule, rule_id)
                if rule is None:
                    return
                session.delete(rule)
                session.commit()
            except SQLAlchemyError as exc:
                session.rollback()
                raise StorageError(f"Failed to delete rule {rule_id}: {exc}") from exc
