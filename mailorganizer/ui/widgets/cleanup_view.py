"""Cleanup-Ansicht: zeigt vor jeder Aktion genau, welche Mails betroffen sind
(einzeln abwählbar), statt eine unwiderrufliche Löschung blind anzudrohen.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from mailorganizer.models.database import Mail
from mailorganizer.services.storage_service import StorageService
from mailorganizer.utils.exceptions import MailOrganizerError

DEFAULT_ARCHIVE_DAYS = 90


def _describe(mail: Mail) -> str:
    return f"{mail.sender} — {mail.subject} ({mail.received_at.strftime('%d.%m.%Y')})"


class _PreviewSection(QGroupBox):
    """One cleanup category: checkbox list of affected mails, all pre-checked, individually toggleable."""

    def __init__(self, title: str, parent=None):
        super().__init__(title, parent)
        layout = QVBoxLayout(self)
        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        layout.addWidget(self.list_widget)

        toggle_row = QHBoxLayout()
        select_all_btn = QPushButton("Alle auswählen")
        select_none_btn = QPushButton("Keine auswählen")
        select_all_btn.clicked.connect(lambda: self._set_all_checked(True))
        select_none_btn.clicked.connect(lambda: self._set_all_checked(False))
        toggle_row.addWidget(select_all_btn)
        toggle_row.addWidget(select_none_btn)
        toggle_row.addStretch(1)
        layout.addLayout(toggle_row)

        self._mail_ids: list[int] = []

    def set_mails(self, mails: list[Mail]) -> None:
        self.list_widget.clear()
        self._mail_ids = []
        for mail in mails:
            item = QListWidgetItem(_describe(mail))
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            self.list_widget.addItem(item)
            self._mail_ids.append(mail.id)
        self.setTitle(f"{self._base_title()} ({len(mails)})")

    def _base_title(self) -> str:
        return self.title().split(" (")[0]

    def _set_all_checked(self, checked: bool) -> None:
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for i in range(self.list_widget.count()):
            self.list_widget.item(i).setCheckState(state)

    def checked_mail_ids(self) -> list[int]:
        result = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                result.append(self._mail_ids[i])
        return result


class CleanupView(QWidget):
    """Tab-Ansicht: alte Mails archivieren, Spam löschen, Duplikate entfernen — mit Vorschau."""

    def __init__(self, storage: StorageService, parent=None):
        super().__init__(parent)
        self.storage = storage
        self.user_id: int | None = None

        layout = QVBoxLayout(self)

        header_row = QHBoxLayout()
        header_row.addWidget(QLabel("Archivieren, älter als:"))
        self.days_spin = QSpinBox()
        self.days_spin.setRange(1, 3650)
        self.days_spin.setValue(DEFAULT_ARCHIVE_DAYS)
        self.days_spin.valueChanged.connect(self.refresh)
        header_row.addWidget(self.days_spin)
        header_row.addWidget(QLabel("Tage"))
        header_row.addStretch(1)
        self.refresh_button = QPushButton("Vorschau aktualisieren")
        self.refresh_button.clicked.connect(self.refresh)
        header_row.addWidget(self.refresh_button)
        layout.addLayout(header_row)

        self.old_section = _PreviewSection("Alte Mails (werden archiviert)")
        self.spam_section = _PreviewSection("Spam (wird gelöscht — unwiderruflich)")
        self.duplicate_section = _PreviewSection("Duplikate (werden gelöscht — unwiderruflich, jeweils die ältere Kopie)")
        for section in (self.old_section, self.spam_section, self.duplicate_section):
            layout.addWidget(section)

        self.run_button = QPushButton("Ausgewählte Aktionen jetzt ausführen")
        self.run_button.clicked.connect(self._run_selected)
        layout.addWidget(self.run_button)

        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

    def set_user_id(self, user_id: int) -> None:
        self.user_id = user_id
        self.refresh()

    def refresh(self) -> None:
        if self.user_id is None:
            return
        self.old_section.set_mails(self.storage.preview_old_mails(self.user_id, self.days_spin.value()))
        self.spam_section.set_mails(self.storage.preview_spam_mails(self.user_id))
        self.duplicate_section.set_mails(self.storage.preview_duplicate_mails(self.user_id))
        self.status_label.setText("")

    def _run_selected(self) -> None:
        if self.user_id is None:
            return
        archive_ids = self.old_section.checked_mail_ids()
        spam_ids = self.spam_section.checked_mail_ids()
        duplicate_ids = self.duplicate_section.checked_mail_ids()

        total = len(archive_ids) + len(spam_ids) + len(duplicate_ids)
        if total == 0:
            QMessageBox.information(self, "Hinweis", "Keine Mails ausgewählt.")
            return

        delete_count = len(spam_ids) + len(duplicate_ids)
        confirm_text = f"{len(archive_ids)} Mail(s) archivieren"
        if delete_count:
            confirm_text += f" und {delete_count} Mail(s) UNWIDERRUFLICH löschen"
        confirm_text += ". Fortfahren?"

        if QMessageBox.question(self, "Bestätigung", confirm_text) != QMessageBox.StandardButton.Yes:
            return

        try:
            for mail_id in archive_ids:
                self.storage.set_mail_flags(mail_id, is_archived=True)
            for mail_id in spam_ids:
                self.storage.hard_delete_mail(mail_id)
            for mail_id in duplicate_ids:
                self.storage.hard_delete_mail(mail_id)
        except MailOrganizerError as exc:
            QMessageBox.critical(self, "Fehler", str(exc))
            return

        self.status_label.setText(
            f"Erledigt: {len(archive_ids)} archiviert, {delete_count} gelöscht."
        )
        self.refresh()
