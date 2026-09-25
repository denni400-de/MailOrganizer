"""Main application window: tabbed layout (Postfach, Bericht, Cleanup, Benchmark, Chat,
Einstellungen) instead of popup dialogs, so nothing has to be re-opened or gets cut off.
"""

from __future__ import annotations

import json

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from mailorganizer.config.settings import Settings, get_settings
from mailorganizer.models.database import Mail, User
from mailorganizer.models.mail import MailData
from mailorganizer.services.analysis_service import AnalysisService
from mailorganizer.services.mail_service import MailAccountCredentials, MailService
from mailorganizer.services.ollama_service import OllamaService
from mailorganizer.services.rules_service import RulesEngine
from mailorganizer.services.storage_service import StorageService
from mailorganizer.services.webhook_service import WebhookError, WebhookService
from mailorganizer.ui.theme import apply_theme
from mailorganizer.ui.widgets.benchmark_dialog import BenchmarkView
from mailorganizer.ui.widgets.chat_panel import ChatView
from mailorganizer.ui.widgets.cleanup_view import CleanupView
from mailorganizer.ui.widgets.folder_panel import FolderPanel
from mailorganizer.ui.widgets.integrations_panel import load_webhook_config
from mailorganizer.ui.widgets.mail_list import MailListWidget
from mailorganizer.ui.widgets.preview_panel import PreviewPanel
from mailorganizer.ui.widgets.report_dialog import ReportView
from mailorganizer.ui.widgets.settings_panel import SettingsView
from mailorganizer.ui.widgets.status_bar import AppStatusBar
from mailorganizer.ui.widgets.ui_settings_panel import load_ui_preferences
from mailorganizer.utils.crypto import decrypt_password, encrypt_password
from mailorganizer.utils.exceptions import MailOrganizerError
from mailorganizer.utils.logger import get_logger

logger = get_logger("main_window")


class MainWindow(QMainWindow):
    """Top-level window: a tab per feature area, plus a slim toolbar for Sync/Analysieren."""

    def __init__(self, settings: Settings | None = None, parent=None):
        super().__init__(parent)
        self.settings = settings or get_settings()
        self.setWindowTitle("Mail Organizer")
        self.resize(1200, 750)

        self.storage = StorageService(self.settings.resolved_database_path)
        self.user_id: int | None = None
        self.mail_credentials: MailAccountCredentials | None = None

        self._build_ui()
        self._build_toolbar()

        self.sync_timer = QTimer(self)
        self.sync_timer.setInterval(self.settings.auto_sync_interval * 1000)
        self.sync_timer.timeout.connect(self.sync_mails)

        if not self._load_stored_account():
            self.tabs.setCurrentWidget(self.settings_view)

    # -- UI construction -----------------------------------------------

    def _build_ui(self) -> None:
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self._build_mailbox_tab()

        self.report_view = ReportView(self.storage)
        self.tabs.addTab(self.report_view, "📊 Bericht")

        self.cleanup_view = CleanupView(self.storage)
        self.tabs.addTab(self.cleanup_view, "🗑️ Cleanup")

        self.benchmark_view = BenchmarkView(self.storage)
        self.tabs.addTab(self.benchmark_view, "🏁 Benchmark")

        self.chat_view = ChatView(self.storage)
        self.tabs.addTab(self.chat_view, "💬 Chat")

        self.settings_view = SettingsView(self.storage, self.user_id)
        self.settings_view.settings_saved.connect(self._on_settings_saved)
        self.tabs.addTab(self.settings_view, "⚙️ Einstellungen")

        self.tabs.currentChanged.connect(self._on_tab_changed)

        self.status_bar_widget = AppStatusBar()
        self.setStatusBar(self.status_bar_widget)

    def _build_mailbox_tab(self) -> None:
        mailbox = QWidget()
        layout = QVBoxLayout(mailbox)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.folder_panel = FolderPanel()
        self.mail_list = MailListWidget()
        self.preview_panel = PreviewPanel()
        splitter.addWidget(self.folder_panel)
        splitter.addWidget(self.mail_list)
        splitter.addWidget(self.preview_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 2)
        splitter.setStretchFactor(2, 3)

        layout.addWidget(splitter)

        self.folder_panel.folder_selected.connect(self._on_folder_selected)
        self.mail_list.mail_selected.connect(self._on_mail_selected)
        self.mail_list.archive_sender_requested.connect(self._on_archive_sender_requested)

        self.tabs.addTab(mailbox, "📬 Postfach")

    def _build_toolbar(self) -> None:
        toolbar = self.addToolBar("Aktionen")

        sync_btn = QPushButton("🔄 Sync")
        sync_btn.clicked.connect(self.sync_mails)
        toolbar.addWidget(sync_btn)

        analyze_btn = QPushButton("🧠 Analysieren")
        analyze_btn.clicked.connect(self.analyze_new_mails)
        toolbar.addWidget(analyze_btn)

        load_folders_btn = QPushButton("📁 Ordner laden")
        load_folders_btn.clicked.connect(self.load_folders)
        toolbar.addWidget(load_folders_btn)

    def _on_tab_changed(self, index: int) -> None:
        if self.user_id is None:
            return
        widget = self.tabs.widget(index)
        if widget in (self.report_view, self.cleanup_view, self.benchmark_view):
            widget.refresh() if hasattr(widget, "refresh") else None

    # -- Account loading -----------------------------------------------

    def _load_stored_account(self) -> bool:
        """Load the first stored user account and wire up credentials, if any exists."""
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

        self._wire_up_user_id()
        self.sync_timer.start()
        self._apply_stored_theme()
        self._refresh_mail_list()
        return True

    def _wire_up_user_id(self) -> None:
        if self.user_id is None:
            return
        self.folder_panel.set_folders(self.storage.list_known_folders(self.user_id))
        self.report_view.set_user_id(self.user_id)
        self.cleanup_view.set_user_id(self.user_id)
        self.benchmark_view.set_user_id(self.user_id)
        self.chat_view.set_user_id(self.user_id)
        self.settings_view.set_user_id(self.user_id)

    def _apply_stored_theme(self) -> None:
        if self.user_id is None:
            return
        theme, font_size, _language = load_ui_preferences(self.storage, self.user_id)
        app = QApplication.instance()
        if app is not None:
            apply_theme(app, theme, font_size)

    # -- Settings ---------------------------------------------------------

    def _on_settings_saved(self) -> None:
        mail_values = self.settings_view.mail_values()
        ollama_values = self.settings_view.ollama_values()

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
            self._wire_up_user_id()
            self._apply_stored_theme()
            self.sync_timer.start()
            self.settings_view.show_status("✅ Gespeichert.")
            self.sync_mails()
        except MailOrganizerError as exc:
            self.settings_view.show_status(f"❌ Fehler: {exc}")
            QMessageBox.critical(self, "Fehler", str(exc))

    # -- Sync & analysis ---------------------------------------------------

    def sync_mails(self) -> None:
        if self.mail_credentials is None or self.user_id is None:
            return
        folder = self.folder_panel.selected_folder() or "INBOX"
        try:
            with MailService(self.mail_credentials) as mail_service:
                self.status_bar_widget.set_connected(True)
                mails = mail_service.fetch_mails(folder=folder, limit=50)
                for mail in mails:
                    mail.folder = folder
                    self.storage.save_mail(self.user_id, mail)
            self._refresh_mail_list()
        except MailOrganizerError as exc:
            self.status_bar_widget.set_connected(False)
            QMessageBox.warning(self, "Sync-Fehler", str(exc))

    def load_folders(self) -> None:
        if self.mail_credentials is None:
            QMessageBox.information(self, "Hinweis", "Bitte zuerst ein Mail-Konto einrichten.")
            return
        try:
            with MailService(self.mail_credentials) as mail_service:
                folders = mail_service.list_folders()
            self.folder_panel.set_folders(folders)
        except MailOrganizerError as exc:
            QMessageBox.warning(self, "Ordner konnten nicht geladen werden", str(exc))

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
        folder = self.folder_panel.selected_folder() or None
        mails = self.storage.list_mails(self.user_id, folder=folder)
        if sort_by_importance:
            mails = sorted(
                mails,
                key=lambda m: m.analysis.importance_score if m.analysis else 0,
                reverse=True,
            )
        self.mail_list.set_mails(mails)
        unread = sum(1 for m in mails if not m.is_read)
        self.status_bar_widget.set_counts(len(mails), unread)

    def _on_folder_selected(self, _folder: str) -> None:
        self._refresh_mail_list()

    def _on_archive_sender_requested(self, sender: str) -> None:
        if self.user_id is None:
            return
        count = self.storage.archive_mails_by_sender(self.user_id, sender)
        if count:
            self._refresh_mail_list()

    def _on_mail_selected(self, mail_id: int) -> None:
        with self.storage.session() as session:
            mail = session.scalar(select(Mail).options(joinedload(Mail.analysis)).where(Mail.id == mail_id))
            self.preview_panel.set_mail(mail)
