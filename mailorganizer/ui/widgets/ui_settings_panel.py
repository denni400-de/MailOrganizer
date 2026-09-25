"""Tab 4: UI-Einstellungen — Dark/Light Mode, Schriftgröße, Analyse-Sprache."""

from __future__ import annotations

from PyQt6.QtWidgets import QApplication, QComboBox, QFormLayout, QSpinBox, QWidget

from mailorganizer.services.storage_service import StorageService
from mailorganizer.ui.theme import apply_theme

_SETTING_THEME = "ui_theme"
_SETTING_FONT_SIZE = "ui_font_size"
_SETTING_ANALYSIS_LANGUAGE = "analysis_language"

ANALYSIS_LANGUAGES = ["auto", "Deutsch", "English", "Français", "Español"]


class UiSettingsTab(QWidget):
    """Dark/Light-Theme, Schriftgröße und Analyse-Sprache — angewendet sofort bei Änderung."""

    def __init__(self, storage: StorageService, user_id: int | None, parent=None):
        super().__init__(parent)
        self.storage = storage
        self.user_id = user_id

        layout = QFormLayout(self)

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["dark", "light"])
        self.theme_combo.currentTextChanged.connect(self._apply_preview)

        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(8, 24)
        self.font_size_spin.setValue(10)
        self.font_size_spin.valueChanged.connect(self._apply_preview)

        self.language_combo = QComboBox()
        self.language_combo.addItems(ANALYSIS_LANGUAGES)

        layout.addRow("Theme:", self.theme_combo)
        layout.addRow("Schriftgröße:", self.font_size_spin)
        layout.addRow("Analyse-Sprache:", self.language_combo)

        if self.user_id is None:
            self.setEnabled(False)
        else:
            self._load()

    def set_user_id(self, user_id: int) -> None:
        self.user_id = user_id
        self.setEnabled(True)
        self._load()

    def _load(self) -> None:
        if self.user_id is None:
            return
        self.theme_combo.setCurrentText(self.storage.get_setting(self.user_id, _SETTING_THEME, "dark") or "dark")
        self.font_size_spin.setValue(int(self.storage.get_setting(self.user_id, _SETTING_FONT_SIZE, "10") or 10))
        self.language_combo.setCurrentText(
            self.storage.get_setting(self.user_id, _SETTING_ANALYSIS_LANGUAGE, "auto") or "auto"
        )

    def _apply_preview(self) -> None:
        app = QApplication.instance()
        if app is not None:
            apply_theme(app, self.theme_combo.currentText(), self.font_size_spin.value())

    def save(self) -> None:
        if self.user_id is None:
            return
        self.storage.set_setting(self.user_id, _SETTING_THEME, self.theme_combo.currentText())
        self.storage.set_setting(self.user_id, _SETTING_FONT_SIZE, str(self.font_size_spin.value()))
        self.storage.set_setting(self.user_id, _SETTING_ANALYSIS_LANGUAGE, self.language_combo.currentText())


def load_ui_preferences(storage: StorageService, user_id: int) -> tuple[str, int, str]:
    """Return (theme, font_size, analysis_language) persisted for `user_id`."""
    theme = storage.get_setting(user_id, _SETTING_THEME, "dark") or "dark"
    font_size = int(storage.get_setting(user_id, _SETTING_FONT_SIZE, "10") or 10)
    language = storage.get_setting(user_id, _SETTING_ANALYSIS_LANGUAGE, "auto") or "auto"
    return theme, font_size, language
