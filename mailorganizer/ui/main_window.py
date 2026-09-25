"""Main application window wiring together services and widgets."""

from __future__ import annotations

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)
from PyQt6.QtCore import Qt

from mailorganizer.config.settings import Settings, get_settings
from mailorganizer.models.database import Mail
from mailorganizer.services.analysis_service import AnalysisService
from mailorganizer.services.mail_service import MailAccountCredentials, MailService
from mailorganizer.services.ollama_service import OllamaService
from mailorganizer.services.rules_service import RulesEngine
from mailorganizer.services.storage_service import StorageService
from mailorganizer.services.webhook_service import WebhookError, WebhookService
from mailorganizer.ui.widgets.benchmark_dialog import BenchmarkDialog
from mailorganizer.ui.widgets.cleanup_dialog import CleanupDialog
from mailorganizer.ui.widgets.integrations_panel import load_webhook_config
from mailorganizer.ui.widgets.mail_list import MailListWidget
from mailorganizer.ui.widgets.preview_panel import PreviewPanel
from mailorganizer.ui.widgets.report_dialog import ReportDialog
from mailorganizer.ui.widgets.settings_panel import SettingsDialog
from mailorganizer.ui.widgets.status_bar import AppStatusBar
from mailorganizer.ui.widgets.ui_settings_panel import load_ui_preferences
from mailorganizer.ui.theme import apply_theme
from mailorganizer.utils.crypto import decrypt_password, encrypt_password
from mailorganizer.utils.exceptions import MailOrganizerError
from mailorganizer.utils.logger import get_logger

logger = get_logger("main_window")


class MainWindow(QMainWindow):
    """Top-level window: toolbar, mail list + preview split, status bar."""

    def __init__(self, settings: Settings | None = None, parent=None):
        super().__init__(parent)
        self.settings = settings or get_settings()
        self.setWindowTitle("Mail Organizer")
        self.resize(1100, 700)

        self.storage = StorageService(self.settings.resolved_database_path)
        self.user_id: int | None = None
        self.mail_credentials: MailAccountCredentials | None = None

        self._build_ui()
        self._build_toolbar()

        self.sync_timer = QTimer(self)
        self.sync_timer.setInterval(self.settings.auto_sync_interval * 1000)
        self.sync_timer.timeout.connect(self.sync_mails)

        if not self._load_stored_account():
            QTimer.singleShot(200, self.open_settings)

    def _build_ui(self) -> None:
        central = QWidget()
        layout = QVBoxLayout(central)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.mail_list = MailListWidget()
        self.preview_panel = PreviewPanel()
        splitter.addWidget(self.mail_list)
        splitter.addWidget(self.preview_panel)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)

        layout.addWidget(splitter)
        self.setCentralWidget(central)

        self.mail_list.mail_selected.connect(self._on_mail_selected)
        self.mail_list.archive_sender_requested.connect(self._on_archive_sender_requested)

        self.status_bar_widget = AppStatusBar()
        self.setStatusBar(self.status_bar_widget)

    def _build_toolbar(self) -> None:
        toolbar = QWidget()
        layout = QHBoxLayout(toolbar)

        settings_btn = QPushButton("⚙️ Einstellungen")
        settings_btn.clicked.connect(self.open_settings)

        sync_btn = QPushButton("🔄 Sync")
        sync_btn.clicked.connect(self.sync_mails)

        analyze_btn = QPushButton("🧠 Analysieren")
        analyze_btn.clicked.connect(self.analyze_new_mails)

        cleanup_btn = QPushButton("🗑️ Cleanup")
        cleanup_btn.clicked.connect(self.open_cleanup)

        report_btn = QPushButton("📊 Bericht")
        report_btn.clicked.connect(self.open_report)

        benchmark_btn = QPushButton("🏁 Benchmark")
        benchmark_btn.clicked.connect(self.open_benchmark)

        for btn in (settings_btn, sync_btn, analyze_btn, cleanup_btn, report_btn, benchmark_btn):
            layout.addWidget(btn)
        layout.addStretch(1)

        dock_container = self.addToolBar("Aktionen")
        dock_container.addWidget(toolbar)

    def _load_stored_account(self) -> bool:
        """Load the first stored user account and wire up credentials, if any exists."""
        from sqlalchemy import select

        from mailorganizer.models.database import User

        with self.storage.session() as session:
            user = session.scalar(select(User))
            if user is None:
                return False

            self.user_id = user.id
            master_key = self.settings.mailorganizer_master_key
            try:
                password = decrypt_password(user.password_encrypted, master_key) if master_key else user.password_encrypted
            except MailOrganizerError as exc:
                logger.error("Failed to decrypt stored password: %s", exc)
                return False

            self.mail_credentials = MailAccountCredentials(
                email_address=user.email_address,
                password=password,
                imap_server=user.imap_server,
                imap_port=user.imap_port,
                smtp_server=user.smtp_server,
                smtp_port=user.smtp_port,
            )
        self.sync_timer.start()
        self._apply_stored_theme()
        self._refresh_mail_list()
        return True

    def _apply_stored_theme(self) -> None:
        if self.user_id is None:
            return
        from PyQt6.QtWidgets import QApplication

        theme, font_size, _language = load_ui_preferences(self.storage, self.user_id)
        app = QApplication.instance()
        if app is not None:
            apply_theme(app, theme, font_size)

    # -- Settings ---------------------------------------------------------

    def open_settings(self) -> None:
        dialog = SettingsDialog(self, storage=self.storage, user_id=self.user_id)
        if dialog.exec():
            self._apply_settings(dialog)
            self._apply_stored_theme()

    def open_cleanup(self) -> None:
        if self.user_id is None:
            QMessageBox.information(self, "Hinweis", "Bitte zuerst ein Mail-Konto einrichten.")
            return
        dialog = CleanupDialog(self.storage, self.user_id, self)
        if dialog.exec():
            self._refresh_mail_list(sort_by_importance=dialog.sort_by_importance)

    def open_report(self) -> None:
        if self.user_id is None:
            QMessageBox.information(self, "Hinweis", "Bitte zuerst ein Mail-Konto einrichten.")
            return
        dialog = ReportDialog(self.storage, self.user_id, self)
        dialog.exec()

    def open_benchmark(self) -> None:
        if self.user_id is None:
            QMessageBox.information(self, "Hinweis", "Bitte zuerst ein Mail-Konto einrichten.")
            return
        ollama_config = self.storage.get_ollama_config(self.user_id)
        ollama_url = ollama_config.ollama_url if ollama_config else "http://localhost:11434"
        dialog = BenchmarkDialog(self.storage, self.user_id, ollama_url, self)
        dialog.exec()

    def _apply_settings(self, dialog: SettingsDialog) -> None:
        mail_values = dialog.mail_values()
        ollama_values = dialog.ollama_values()

        master_key = self.settings.mailorganizer_master_key
        try:
            if master_key:
                password_encrypted = encrypt_password(mail_values.password, master_key)
            else:
                password_encrypted = mail_values.password
                logger.warning("No master key configured; storing password unencrypted")

            user = self.storage.get_or_create_user(
                email_address=mail_values.email_address,
                imap_server=mail_values.imap_server,
                smtp_server=mail_values.smtp_server,
                password_encrypted=password_encrypted,
                imap_port=mail_values.imap_port,
                smtp_port=mail_values.smtp_port,
            )
            self.user_id = user.id
            self.storage.save_ollama_config(
                user_id=user.id,
                ollama_url=ollama_values.ollama_url,
                ollama_model=ollama_values.ollama_model,
                temperature=ollama_values.temperature,
                max_tokens=ollama_values.max_tokens,
            )
            self.mail_credentials = MailAccountCredentials(
                email_address=mail_values.email_address,
                password=mail_values.password,
                imap_server=mail_values.imap_server,
                imap_port=mail_values.imap_port,
                smtp_server=mail_values.smtp_server,
                smtp_port=mail_values.smtp_port,
            )
            self.sync_timer.start()
            self.sync_mails()
        except MailOrganizerError as exc:
            QMessageBox.critical(self, "Fehler", str(exc))

    # -- Sync & analysis ---------------------------------------------------

    def sync_mails(self) -> None:
        if self.mail_credentials is None or self.user_id is None:
            return
        try:
            with MailService(self.mail_credentials) as mail_service:
                self.status_bar_widget.set_connected(True)
                mails = mail_service.fetch_mails(limit=50)
                for mail in mails:
                    self.storage.save_mail(self.user_id, mail)
            self._refresh_mail_list()
        except MailOrganizerError as exc:
            self.status_bar_widget.set_connected(False)
            QMessageBox.warning(self, "Sync-Fehler", str(exc))

    def analyze_new_mails(self) -> None:
        if self.user_id is None:
            return
        ollama_config = self.storage.get_ollama_config(self.user_id)
        if ollama_config is None:
            QMessageBox.information(self, "Hinweis", "Bitte zuerst Ollama in den Einstellungen konfigurieren.")
            return

        ollama_service = OllamaService(base_url=ollama_config.ollama_url)
        analysis_service = AnalysisService(
            ollama_service=ollama_service,
            model=ollama_config.ollama_model,
            temperature=ollama_config.temperature,
            max_tokens=ollama_config.max_tokens,
        )

        db_mails = [m for m in self.storage.list_mails(self.user_id) if m.analysis is None]
        if not db_mails:
            return

        _theme, _font_size, analysis_language = load_ui_preferences(self.storage, self.user_id)

        progress = QProgressDialog("Analysiere Mails...", "Abbrechen", 0, len(db_mails), self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)

        from mailorganizer.models.mail import MailData
        import json

        for i, db_mail in enumerate(db_mails):
            if progress.wasCanceled():
                break
            progress.setValue(i)
            mail_data = MailData(
                message_id=db_mail.message_id,
                sender=db_mail.sender,
                recipients=json.loads(db_mail.recipients or "[]"),
                subject=db_mail.subject,
                received_at=db_mail.received_at,
                body=db_mail.body or "",
                html_body=db_mail.html_body or "",
            )
            try:
                result = analysis_service.analyze_mail(mail_data, user_language=analysis_language)
                analysis_row = self.storage.save_analysis(db_mail.id, result)
                self._notify_webhook_if_important(db_mail, analysis_row)
            except MailOrganizerError as exc:
                logger.error("Analysis failed for mail %s: %s", db_mail.id, exc)

        progress.setValue(len(db_mails))

        rules_engine = RulesEngine(self.storage)
        affected = rules_engine.run_for_user(self.user_id)
        if affected:
            logger.info("Analyse-Regeln angewendet auf %s Mails", affected)

        self._refresh_mail_list()

    def _notify_webhook_if_important(self, mail: Mail, analysis) -> None:
        if self.user_id is None:
            return
        config = load_webhook_config(self.storage, self.user_id)
        service = WebhookService(config)
        try:
            service.notify_if_important(mail, analysis)
        except WebhookError as exc:
            logger.error("Webhook-Benachrichtigung fehlgeschlagen: %s", exc)

    # -- List / preview -----------------------------------------------

    def _refresh_mail_list(self, sort_by_importance: bool = False) -> None:
        if self.user_id is None:
            return
        mails = self.storage.list_mails(self.user_id)
        if sort_by_importance:
            mails = sorted(
                mails,
                key=lambda m: m.analysis.importance_score if m.analysis else 0,
                reverse=True,
            )
        self.mail_list.set_mails(mails)
        unread = sum(1 for m in mails if not m.is_read)
        self.status_bar_widget.set_counts(len(mails), unread)

    def _on_archive_sender_requested(self, sender: str) -> None:
        if self.user_id is None:
            return
        count = self.storage.archive_mails_by_sender(self.user_id, sender)
        if count:
            self._refresh_mail_list()

    def _on_mail_selected(self, mail_id: int) -> None:
        from sqlalchemy import select
        from sqlalchemy.orm import joinedload

        with self.storage.session() as session:
            mail = session.scalar(select(Mail).options(joinedload(Mail.analysis)).where(Mail.id == mail_id))
            self.preview_panel.set_mail(mail)
