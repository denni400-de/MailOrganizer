"""Central logging setup for MailOrganizer."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from mailorganizer.config import constants

_CONFIGURED = False


def setup_logging(log_level: str = "INFO", log_dir: Path | None = None) -> None:
    """Configure the root 'mailorganizer' logger once with console + rotating file handlers."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    log_dir = log_dir or Path(constants.LOG_DIR).expanduser()
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "app.log"

    logger = logging.getLogger("mailorganizer")
    logger.setLevel(log_level.upper())

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    file_handler = RotatingFileHandler(log_file, maxBytes=5 * 1024 * 1024, backupCount=3)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Return a namespaced logger under the 'mailorganizer' hierarchy."""
    if not _CONFIGURED:
        setup_logging()
    return logging.getLogger(f"mailorganizer.{name}")
