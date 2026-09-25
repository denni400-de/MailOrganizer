"""Applies the dark/light QSS stylesheets and base font to the running QApplication."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication

_STYLES_DIR = Path(__file__).parent / "styles"

THEMES = {"dark": "dark_theme.qss", "light": "light_theme.qss"}


def load_stylesheet(theme: str) -> str:
    """Return the QSS content for `theme` ("dark" or "light"), or "" if unknown."""
    filename = THEMES.get(theme)
    if filename is None:
        return ""
    path = _STYLES_DIR / filename
    return path.read_text(encoding="utf-8") if path.exists() else ""


def apply_theme(app: QApplication, theme: str, font_size: int | None = None) -> None:
    """Apply the given theme's stylesheet and optional base font size to `app`."""
    app.setStyleSheet(load_stylesheet(theme))
    if font_size:
        font = app.font()
        font.setPointSize(font_size)
        app.setFont(font)
