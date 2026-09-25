"""Settings view: Mail account, Ollama configuration, analysis rules, integrations, UI.

Embedded as the "Einstellungen" tab in MainWindow (not a popup dialog) with an explicit
"Speichern" button — settings_saved fires with the mail/Ollama values so MainWindow can
create/update the account.
"""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from mailorganizer.services.mail_service import MailAccountCredentials, MailService
from mailorganizer.services.ollama_service import OllamaService
from mailorganizer.services.storage_service import StorageService
from mailorganizer.ui.widgets.integrations_panel import IntegrationsTab
from mailorganizer.ui.widgets.rules_panel import AnalysisRulesTab
from mailorganizer.ui.widgets.ui_settings_panel import UiSettingsTab
from mailorganizer.ui.workers import run_in_background


def _test_mail_connection(credentials: MailAccountCredentials) -> bool:
    with MailService(credentials):
        pass
    return True


@dataclass
class MailSettingsValues:
    imap_server: str
    imap_port: int
    smtp_server: str
    smtp_port: int
    email_address: str
    password: str


@dataclass
class OllamaSettingsValues:
    ollama_url: str
    ollama_model: str
    temperature: float
    max_tokens: int


class MailSettingsTab(QWidget):
    """Tab 1: Mail-Einstellungen."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QFormLayout(self)

        self.imap_server_edit = QLineEdit()
        self.imap_port_spin = QSpinBox()
        self.imap_port_spin.setRange(1, 65535)
        self.imap_port_spin.setValue(993)

        self.smtp_server_edit = QLineEdit()
        self.smtp_port_spin = QSpinBox()
        self.smtp_port_spin.setRange(1, 65535)
        self.smtp_port_spin.setValue(587)

        self.email_edit = QLineEdit()
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)

        self.test_button = QPushButton("Verbindungs-Test")
        self.test_result_label = QLabel("")
        self.test_button.clicked.connect(self._test_connection)

        layout.addRow("IMAP-Server:", self.imap_server_edit)
        layout.addRow("IMAP-Port:", self.imap_port_spin)
        layout.addRow("SMTP-Server:", self.smtp_server_edit)
        layout.addRow("SMTP-Port:", self.smtp_port_spin)
        layout.addRow("E-Mail:", self.email_edit)
        layout.addRow("Passwort:", self.password_edit)
        layout.addRow(self.test_button)
        layout.addRow(self.test_result_label)

    def values(self) -> MailSettingsValues:
        return MailSettingsValues(
            imap_server=self.imap_server_edit.text().strip(),
            imap_port=self.imap_port_spin.value(),
            smtp_server=self.smtp_server_edit.text().strip(),
            smtp_port=self.smtp_port_spin.value(),
            email_address=self.email_edit.text().strip(),
            password=self.password_edit.text(),
        )

    def load_values(self, values: MailSettingsValues) -> None:
        self.imap_server_edit.setText(values.imap_server)
        self.imap_port_spin.setValue(values.imap_port)
        self.smtp_server_edit.setText(values.smtp_server)
        self.smtp_port_spin.setValue(values.smtp_port)
        self.email_edit.setText(values.email_address)
        self.password_edit.setText(values.password)

    def _test_connection(self) -> None:
        values = self.values()
        try:
            credentials = MailAccountCredentials(
                email_address=values.email_address,
                password=values.password,
                imap_server=values.imap_server,
                imap_port=values.imap_port,
                smtp_server=values.smtp_server,
                smtp_port=values.smtp_port,
            )
        except Exception as exc:  # validation errors etc. — fail fast, no network call needed
            self.test_result_label.setText(f"❌ Fehler: {exc}")
            return

        self.test_button.setEnabled(False)
        self.test_result_label.setText("⏳ Teste Verbindung …")
        run_in_background(
            _test_mail_connection,
            credentials,
            on_success=self._on_test_success,
            on_error=self._on_test_error,
        )

    def _on_test_success(self, _result: bool) -> None:
        self.test_button.setEnabled(True)
        self.test_result_label.setText("✅ Verbindung erfolgreich")

    def _on_test_error(self, message: str) -> None:
        self.test_button.setEnabled(True)
        self.test_result_label.setText(f"❌ Fehler: {message}")


class OllamaSettingsTab(QWidget):
    """Tab 2: Ollama-Konfiguration."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QFormLayout(self)

        self.url_edit = QLineEdit("http://localhost:11434")
        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)

        self.refresh_button = QPushButton("Modelle aktualisieren")
        self.refresh_button.clicked.connect(self._refresh_models)

        self.temperature_spin = QDoubleSpinBox()
        self.temperature_spin.setRange(0.0, 1.0)
        self.temperature_spin.setSingleStep(0.1)
        self.temperature_spin.setValue(0.7)

        self.max_tokens_spin = QSpinBox()
        self.max_tokens_spin.setRange(100, 2000)
        self.max_tokens_spin.setValue(500)

        self.status_label = QLabel("Status: unbekannt")
        self.test_button = QPushButton("Modell-Test")
        self.test_button.clicked.connect(self._test_model)

        layout.addRow("Ollama-URL:", self.url_edit)
        layout.addRow("Modell:", self.model_combo)
        layout.addRow(self.refresh_button)
        layout.addRow("Temperatur:", self.temperature_spin)
        layout.addRow("Max Tokens:", self.max_tokens_spin)
        layout.addRow(self.test_button)
        layout.addRow(self.status_label)

    def values(self) -> OllamaSettingsValues:
        return OllamaSettingsValues(
            ollama_url=self.url_edit.text().strip(),
            ollama_model=self.model_combo.currentText().strip(),
            temperature=self.temperature_spin.value(),
            max_tokens=self.max_tokens_spin.value(),
        )

    def load_values(self, values: OllamaSettingsValues) -> None:
        self.url_edit.setText(values.ollama_url)
        self.model_combo.setCurrentText(values.ollama_model)
        self.temperature_spin.setValue(values.temperature)
        self.max_tokens_spin.setValue(values.max_tokens)

    def _service(self) -> OllamaService:
        return OllamaService(base_url=self.url_edit.text().strip())

    def _refresh_models(self) -> None:
        self.refresh_button.setEnabled(False)
        self.status_label.setText("Status: ⏳ Lade Modelle …")
        run_in_background(
            self._service().list_models,
            on_success=self._on_models_loaded,
            on_error=self._on_models_error,
        )

    def _on_models_loaded(self, models: list[str]) -> None:
        self.refresh_button.setEnabled(True)
        self.model_combo.clear()
        self.model_combo.addItems(models)
        self.status_label.setText(f"Status: ✅ {len(models)} Modelle gefunden")

    def _on_models_error(self, message: str) -> None:
        self.refresh_button.setEnabled(True)
        self.status_label.setText(f"Status: ❌ {message}")

    def _test_model(self) -> None:
        self.test_button.setEnabled(False)
        self.status_label.setText("Status: ⏳ Teste Verbindung …")
        run_in_background(
            self._service().is_available,
            on_success=self._on_model_test_done,
            on_error=lambda msg: self._on_model_test_done(False),
        )

    def _on_model_test_done(self, available: bool) -> None:
        self.test_button.setEnabled(True)
        if available:
            self.status_label.setText("Status: ✅ Ollama erreichbar")
        else:
            self.status_label.setText("Status: ❌ Ollama nicht erreichbar")


class SettingsView(QWidget):
    """Tabbed settings: Mail, Ollama, Analyse-Regeln, Integrationen, UI — with a Speichern-Button."""

    settings_saved = pyqtSignal()

    def __init__(self, storage: StorageService, user_id: int | None = None, parent=None):
        super().__init__(parent)
        self.storage = storage
        self.user_id = user_id

        layout = QVBoxLayout(self)

        self.banner = QLabel(
            "👋 Noch kein Mail-Konto eingerichtet. Trage unten bei „Mail-Einstellungen“ deinen "
            "IMAP-/SMTP-Zugang ein, bei „Ollama-Konfiguration“ deinen lokalen Ollama-Server, "
            "und klicke dann auf „Speichern“."
        )
        self.banner.setWordWrap(True)
        self.banner.setStyleSheet(
            "background-color: #3b4252; color: #eceff4; padding: 8px; border-radius: 4px;"
        )
        self.banner.setVisible(user_id is None)
        layout.addWidget(self.banner)

        self.tabs = QTabWidget()

        self.mail_tab = MailSettingsTab()
        self.ollama_tab = OllamaSettingsTab()
        self.rules_tab = AnalysisRulesTab(storage, user_id)
        self.integrations_tab = IntegrationsTab(storage, user_id)
        self.ui_tab = UiSettingsTab(storage, user_id)

        self.tabs.addTab(self.mail_tab, "Mail-Einstellungen")
        self.tabs.addTab(self.ollama_tab, "Ollama-Konfiguration")
        self.tabs.addTab(self.rules_tab, "Analyse-Regeln")
        self.tabs.addTab(self.integrations_tab, "Integrationen")
        self.tabs.addTab(self.ui_tab, "UI-Einstellungen")

        layout.addWidget(self.tabs)

        save_row = QVBoxLayout()
        self.save_button = QPushButton("Speichern")
        self.save_button.clicked.connect(self._on_save)
        self.status_label = QLabel("")
        save_row.addWidget(self.save_button)
        save_row.addWidget(self.status_label)
        layout.addLayout(save_row)

    def set_user_id(self, user_id: int) -> None:
        self.user_id = user_id
        self.rules_tab.set_user_id(user_id)
        self.integrations_tab.set_user_id(user_id)
        self.ui_tab.set_user_id(user_id)
        self.banner.setVisible(False)

    def load_from_account(
        self,
        mail_values: MailSettingsValues,
        ollama_values: OllamaSettingsValues,
    ) -> None:
        self.mail_tab.load_values(mail_values)
        self.ollama_tab.load_values(ollama_values)

    def _on_save(self) -> None:
        self.status_label.setText("")
        self.settings_saved.emit()

    def show_status(self, text: str) -> None:
        self.status_label.setText(text)

    def mail_values(self) -> MailSettingsValues:
        return self.mail_tab.values()

    def ollama_values(self) -> OllamaSettingsValues:
        return self.ollama_tab.values()
