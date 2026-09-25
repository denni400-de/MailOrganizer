"""Settings dialog: Mail account, Ollama configuration, analysis rules, UI preferences."""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
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
from mailorganizer.ui.widgets.rules_panel import AnalysisRulesTab
from mailorganizer.utils.exceptions import MailOrganizerError


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
            with MailService(credentials):
                pass
            self.test_result_label.setText("✅ Verbindung erfolgreich")
        except MailOrganizerError as exc:
            self.test_result_label.setText(f"❌ Fehler: {exc}")


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

    def _service(self) -> OllamaService:
        return OllamaService(base_url=self.url_edit.text().strip())

    def _refresh_models(self) -> None:
        try:
            models = self._service().list_models()
            self.model_combo.clear()
            self.model_combo.addItems(models)
            self.status_label.setText(f"Status: ✅ {len(models)} Modelle gefunden")
        except MailOrganizerError as exc:
            self.status_label.setText(f"Status: ❌ {exc}")

    def _test_model(self) -> None:
        service = self._service()
        if service.is_available():
            self.status_label.setText("Status: ✅ Ollama erreichbar")
        else:
            self.status_label.setText("Status: ❌ Ollama nicht erreichbar")


class SettingsDialog(QDialog):
    """Tabbed settings dialog: Mail, Ollama, Analyse-Regeln, UI."""

    def __init__(self, parent=None, storage: StorageService | None = None, user_id: int | None = None):
        super().__init__(parent)
        self.setWindowTitle("Einstellungen")
        self.resize(520, 460)

        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()

        self.mail_tab = MailSettingsTab()
        self.ollama_tab = OllamaSettingsTab()
        self.ui_placeholder = QLabel("UI-Einstellungen: kommt in einer späteren Version.")

        self.tabs.addTab(self.mail_tab, "Mail-Einstellungen")
        self.tabs.addTab(self.ollama_tab, "Ollama-Konfiguration")

        if storage is not None:
            self.rules_tab = AnalysisRulesTab(storage, user_id)
        else:
            self.rules_tab = QLabel("Bitte zuerst Mail-Konto speichern.")
        self.tabs.addTab(self.rules_tab, "Analyse-Regeln")
        self.tabs.addTab(self.ui_placeholder, "UI-Einstellungen")

        layout.addWidget(self.tabs)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def mail_values(self) -> MailSettingsValues:
        return self.mail_tab.values()

    def ollama_values(self) -> OllamaSettingsValues:
        return self.ollama_tab.values()
