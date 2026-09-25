"""Table widget listing mails (Von | Betreff | Datum)."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QAbstractItemView, QHeaderView, QTableWidget, QTableWidgetItem

from mailorganizer.models.database import Mail


class MailListWidget(QTableWidget):
    """Displays mails in a read-only table and emits mail_selected(mail_id) on click."""

    mail_selected = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(0, 3, parent)
        self.setHorizontalHeaderLabels(["Von", "Betreff", "Datum"])
        self.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setAlternatingRowColors(True)
        self._mail_ids: list[int] = []
        self.itemSelectionChanged.connect(self._on_selection_changed)

    def set_mails(self, mails: list[Mail]) -> None:
        self.setRowCount(0)
        self._mail_ids = []
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

    def _on_selection_changed(self) -> None:
        rows = self.selectionModel().selectedRows()
        if not rows:
            return
        row = rows[0].row()
        if 0 <= row < len(self._mail_ids):
            self.mail_selected.emit(self._mail_ids[row])
