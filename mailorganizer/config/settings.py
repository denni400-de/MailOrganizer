"""Global application configuration loaded from environment variables / .env file."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from mailorganizer.config import constants


class Settings(BaseSettings):
    """Application settings, populated from environment variables or a .env file."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Mail settings
    imap_server: str = Field(default="imap.gmail.com")
    imap_port: int = Field(default=constants.DEFAULT_IMAP_PORT)
    smtp_server: str = Field(default="smtp.gmail.com")
    smtp_port: int = Field(default=constants.DEFAULT_SMTP_PORT)

    # Ollama settings
    ollama_url: str = Field(default=constants.DEFAULT_OLLAMA_URL)
    ollama_model: str = Field(default=constants.DEFAULT_OLLAMA_MODEL)
    ollama_temperature: float = Field(default=constants.DEFAULT_OLLAMA_TEMPERATURE)
    ollama_max_tokens: int = Field(default=constants.DEFAULT_OLLAMA_MAX_TOKENS)

    # App settings
    auto_sync_interval: int = Field(default=constants.DEFAULT_AUTO_SYNC_INTERVAL)
    log_level: str = Field(default="INFO")
    ui_theme: str = Field(default="dark")
    database_path: str = Field(default=constants.DEFAULT_DATABASE_PATH)

    # Security
    encrypt_passwords: bool = Field(default=True)
    backup_enabled: bool = Field(default=True)
    backup_frequency: str = Field(default="weekly")
    mailorganizer_master_key: str | None = Field(default=None)

    @property
    def resolved_database_path(self) -> Path:
        return Path(self.database_path).expanduser()

    @property
    def resolved_log_dir(self) -> Path:
        return Path(constants.LOG_DIR).expanduser()


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
