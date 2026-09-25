"""Integrations tab: configure the Slack/Discord/generic webhook notification (plan 8.5)."""

from __future__ import annotations

import requests
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QWidget,
)

from mailorganizer.services.storage_service import StorageService
from mailorganizer.services.webhook_service import WEBHOOK_FORMATS, WebhookConfig

_SETTING_URL = "webhook_url"
_SETTING_FORMAT = "webhook_format"
_SETTING_ENABLED = "webhook_enabled"
_SETTING_THRESHOLD = "webhook_threshold"


class IntegrationsTab(QWidget):
    """Tab 5: Slack/Discord/Webhook-Benachrichtigungen bei wichtigen Mails."""

    def __init__(self, storage: StorageService, user_id: int | None, parent=None):
        super().__init__(parent)
        self.storage = storage
        self.user_id = user_id

        layout = QFormLayout(self)

        self.enabled_check = QCheckBox("Benachrichtigungen aktivieren")
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("https://hooks.slack.com/services/... oder eigener Webhook")
        self.format_combo = QComboBox()
        self.format_combo.addItems(WEBHOOK_FORMATS)
        self.threshold_spin = QSpinBox()
        self.threshold_spin.setRange(1, 5)
        self.threshold_spin.setValue(4)

        self.test_button = QPushButton("Test senden")
        self.test_button.clicked.connect(self._send_test)
        self.status_label = QLabel("")

        layout.addRow(self.enabled_check)
        layout.addRow("Webhook-URL:", self.url_edit)
        layout.addRow("Format:", self.format_combo)
        layout.addRow("Ab Wichtigkeit:", self.threshold_spin)
        layout.addRow(self.test_button)
        layout.addRow(self.status_label)

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
        self.enabled_check.setChecked(self.storage.get_setting(self.user_id, _SETTING_ENABLED, "false") == "true")
        self.url_edit.setText(self.storage.get_setting(self.user_id, _SETTING_URL, "") or "")
        self.format_combo.setCurrentText(self.storage.get_setting(self.user_id, _SETTING_FORMAT, "generic") or "generic")
        self.threshold_spin.setValue(int(self.storage.get_setting(self.user_id, _SETTING_THRESHOLD, "4") or 4))

    def save(self) -> None:
        if self.user_id is None:
            return
        self.storage.set_setting(self.user_id, _SETTING_ENABLED, "true" if self.enabled_check.isChecked() else "false")
        self.storage.set_setting(self.user_id, _SETTING_URL, self.url_edit.text().strip())
        self.storage.set_setting(self.user_id, _SETTING_FORMAT, self.format_combo.currentText())
        self.storage.set_setting(self.user_id, _SETTING_THRESHOLD, str(self.threshold_spin.value()))

    def _send_test(self) -> None:
        url = self.url_edit.text().strip()
        if not url:
            QMessageBox.information(self, "Hinweis", "Bitte zuerst eine Webhook-URL eintragen.")
            return
        fmt = self.format_combo.currentText()
        if fmt == "slack":
            payload = {"text": "Mail Organizer: Test-Benachrichtigung"}
        elif fmt == "discord":
            payload = {"content": "Mail Organizer: Test-Benachrichtigung"}
        else:
            payload = {"message": "Mail Organizer: Test-Benachrichtigung"}

        try:
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            self.status_label.setText("✅ Test erfolgreich gesendet")
        except requests.RequestException as exc:
            self.status_label.setText(f"❌ Fehler: {exc}")


def load_webhook_config(storage: StorageService, user_id: int) -> WebhookConfig:
    """Build a WebhookConfig from the persisted settings for `user_id`."""
    return WebhookConfig(
        url=storage.get_setting(user_id, _SETTING_URL, "") or "",
        format=storage.get_setting(user_id, _SETTING_FORMAT, "generic") or "generic",
        enabled=storage.get_setting(user_id, _SETTING_ENABLED, "false") == "true",
        importance_threshold=int(storage.get_setting(user_id, _SETTING_THRESHOLD, "4") or 4),
    )
