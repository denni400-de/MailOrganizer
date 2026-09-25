"""SQLAlchemy ORM models implementing the schema from IMPLEMENTATION_PLAN.md section 4."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    imap_server: Mapped[str] = mapped_column(String, nullable=False)
    imap_port: Mapped[int] = mapped_column(Integer, default=993)
    smtp_server: Mapped[str] = mapped_column(String, nullable=False)
    smtp_port: Mapped[int] = mapped_column(Integer, default=587)
    email_address: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    password_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    mails: Mapped[list["Mail"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    settings: Mapped[list["Setting"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    ollama_configs: Mapped[list["OllamaConfig"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    analysis_rules: Mapped[list["AnalysisRule"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Mail(Base):
    __tablename__ = "mails"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    message_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    sender: Mapped[str] = mapped_column(String, nullable=False)
    recipients: Mapped[str] = mapped_column(Text, nullable=False)  # JSON
    cc: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    subject: Mapped[str] = mapped_column(String, nullable=False)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    html_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    is_important: Mapped[bool] = mapped_column(Boolean, default=False)
    is_spam: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    user: Mapped["User"] = relationship(back_populates="mails")
    analysis: Mapped["MailAnalysis | None"] = relationship(
        back_populates="mail", cascade="all, delete-orphan", uselist=False
    )


class MailAnalysis(Base):
    __tablename__ = "mail_analysis"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mail_id: Mapped[int] = mapped_column(ForeignKey("mails.id", ondelete="CASCADE"), nullable=False, unique=True)
    category: Mapped[str | None] = mapped_column(String, nullable=True)
    importance_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sentiment: Mapped[str | None] = mapped_column(String, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    recommended_action: Mapped[str | None] = mapped_column(String, nullable=True)
    keywords: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON array
    ollama_model: Mapped[str] = mapped_column(String, nullable=False)
    analysis_timestamp: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    processing_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    mail: Mapped["Mail"] = relationship(back_populates="analysis")


class Setting(Base):
    __tablename__ = "settings"
    __table_args__ = (UniqueConstraint("user_id", "key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    key: Mapped[str] = mapped_column(String, nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)

    user: Mapped["User"] = relationship(back_populates="settings")


class OllamaConfig(Base):
    __tablename__ = "ollama_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    ollama_url: Mapped[str] = mapped_column(String, default="http://localhost:11434")
    ollama_model: Mapped[str] = mapped_column(String, nullable=False)
    temperature: Mapped[float] = mapped_column(Float, default=0.7)
    max_tokens: Mapped[int] = mapped_column(Integer, default=500)
    last_checked: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)

    user: Mapped["User"] = relationship(back_populates="ollama_configs")


class AnalysisRule(Base):
    __tablename__ = "analysis_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    condition: Mapped[str] = mapped_column(Text, nullable=False)  # JSON
    action: Mapped[str] = mapped_column(String, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    user: Mapped["User"] = relationship(back_populates="analysis_rules")


def init_engine(database_path: str | Path, echo: bool = False):
    """Create a SQLAlchemy engine for the given SQLite database path, ensuring the parent dir exists."""
    path = Path(database_path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{path}", echo=echo, connect_args={"check_same_thread": False})


def create_all(engine) -> None:
    """Create all tables that do not yet exist."""
    Base.metadata.create_all(engine)


def get_session_factory(engine) -> sessionmaker:
    """Return a sessionmaker bound to the given engine."""
    return sessionmaker(bind=engine, expire_on_commit=False)
