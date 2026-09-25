"""Table widget listing mails (Von | Betreff | Datum)."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QAbstractItemView, QHeaderView, QMenu, QTableWidget, QTableWidgetItem

from mailorganizer.models.database import Mail


class MailListWidget(QTableWidget):
    """Displays mails in a read-only table and emits mail_selected(mail_id) on click."""

    mail_selected = pyqtSignal(int)
    archive_sender_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(0, 3, parent)
        self.setHorizontalHeaderLabels(["Von", "Betreff", "Datum"])
        self.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setAlternatingRowColors(True)
        self._mail_ids: list[int] = []
        self._senders: list[str] = []
        self.itemSelectionChanged.connect(self._on_selection_changed)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    def set_mails(self, mails: list[Mail]) -> None:
        self.setRowCount(0)
        self._mail_ids = []
        self._senders = []
        for mail in mails:
            row = self.rowCount()
            self.insertRow(row)
            self.setItem(row, 0, QTableWidgetItem(mail.sender))
            subject_item = QTableWidgetItem(mail.subject)
            if not mail.is_read:
                font = subject_item.font()
                font.setBold(True)
                subject_item.setFont(font)
            self.setItem(row, 1, subject_item)
            self.setItem(row, 2, QTableWidgetItem(mail.received_at.strftime("%d.%m.%Y %H:%M")))
            self._mail_ids.append(mail.id)
            self._senders.append(mail.sender)

    def _on_selection_changed(self) -> None:
        rows = self.selectionModel().selectedRows()
        if not rows:
            return
        row = rows[0].row()
        if 0 <= row < len(self._mail_ids):
            self.mail_selected.emit(self._mail_ids[row])

    def _show_context_menu(self, pos) -> None:
        row = self.rowAt(pos.y())
        if row < 0 or row >= len(self._senders):
            return
        sender = self._senders[row]
        menu = QMenu(self)
        action = menu.addAction(f"Alle Mails von {sender} archivieren")
        chosen = menu.exec(self.viewport().mapToGlobal(pos))
        if chosen == action:
            self.archive_sender_requested.emit(sender)
