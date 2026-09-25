"""Folder sidebar for the Postfach tab: lists IMAP folders and lets the user manage them
individually (select to filter + sync a single folder) instead of only ever seeing INBOX.
"""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QAbstractItemView, QListWidget, QListWidgetItem, QVBoxLayout, QWidget

ALL_FOLDERS = "Alle Ordner"


class FolderPanel(QWidget):
    """Left-hand folder list. Emits folder_selected(name) where name is "" for "Alle Ordner"."""

    folder_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.list_widget.currentTextChanged.connect(self._on_selection_changed)
        layout.addWidget(self.list_widget)

        self.setMaximumWidth(220)

    def set_folders(self, folders: list[str]) -> None:
        """Populate the list with `folders` (e.g. from IMAP or the local DB), plus "Alle Ordner"."""
        current = self.selected_folder()
        self.list_widget.clear()
        self.list_widget.addItem(QListWidgetItem(ALL_FOLDERS))
        for name in folders:
            self.list_widget.addItem(QListWidgetItem(name))

        # Restore the previous selection if it still exists, else default to "Alle Ordner".
        items = [self.list_widget.item(i).text() for i in range(self.list_widget.count())]
        target = current if current in items else ALL_FOLDERS
        self.list_widget.setCurrentRow(items.index(target) if target in items else 0)

    def selected_folder(self) -> str:
        """Return the selected folder name, or "" when "Alle Ordner" is selected."""
        item = self.list_widget.currentItem()
        if item is None or item.text() == ALL_FOLDERS:
            return ""
        return item.text()

    def _on_selection_changed(self, text: str) -> None:
        self.folder_selected.emit("" if text in (ALL_FOLDERS, "") else text)
