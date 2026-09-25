"""Folder sidebar for the Postfach tab: an Outlook-style expandable tree instead of a flat
list, so nested folders (e.g. "INBOX/Archiv/2024") are actually readable.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget

ALL_FOLDERS = "Alle Ordner"
_FOLDER_ROLE = Qt.ItemDataRole.UserRole


def _detect_delimiter(folders: list[str]) -> str | None:
    """Guess the IMAP hierarchy delimiter from the folder names themselves."""
    for candidate in ("/", "."):
        if any(candidate in name for name in folders):
            return candidate
    return None


def _build_tree(tree: QTreeWidget, folders: list[str]) -> None:
    delimiter = _detect_delimiter(folders)
    nodes: dict[tuple[str, ...], QTreeWidgetItem] = {}

    for name in folders:
        parts = tuple(name.split(delimiter)) if delimiter else (name,)
        for depth in range(1, len(parts) + 1):
            path = parts[:depth]
            if path in nodes:
                continue
            label = path[-1]
            if depth == 1:
                item = QTreeWidgetItem(tree, [label])
            else:
                item = QTreeWidgetItem(nodes[path[:-1]], [label])
            # Only a node whose full path matches an actual IMAP folder name is selectable
            # as a sync/filter target — purely structural parent segments are just for grouping.
            full_name = delimiter.join(path) if delimiter else path[0]
            item.setData(0, _FOLDER_ROLE, full_name if full_name in folders else None)
            nodes[path] = item

    tree.expandAll()


class FolderPanel(QWidget):
    """Left-hand folder tree. Emits folder_selected(name) where name is "" for "Alle Ordner"."""

    folder_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.currentItemChanged.connect(self._on_selection_changed)
        layout.addWidget(self.tree)

        self.setMaximumWidth(240)

    def set_folders(self, folders: list[str]) -> None:
        """Populate the tree with `folders` (e.g. from IMAP or the local DB), plus "Alle Ordner"."""
        previous = self.selected_folder()

        self.tree.blockSignals(True)
        self.tree.clear()
        all_item = QTreeWidgetItem(self.tree, [ALL_FOLDERS])
        all_item.setData(0, _FOLDER_ROLE, "")
        _build_tree(self.tree, folders)
        self.tree.blockSignals(False)

        target = self._find_item(previous) if previous else all_item
        self.tree.setCurrentItem(target or all_item)

    def _find_item(self, folder_name: str) -> QTreeWidgetItem | None:
        iterator_stack = [self.tree.topLevelItem(i) for i in range(self.tree.topLevelItemCount())]
        while iterator_stack:
            item = iterator_stack.pop()
            if item is None:
                continue
            if item.data(0, _FOLDER_ROLE) == folder_name:
                return item
            iterator_stack.extend(item.child(i) for i in range(item.childCount()))
        return None

    def selected_folder(self) -> str:
        """Return the selected folder's full IMAP name, or "" when "Alle Ordner" (or nothing
        selectable) is selected."""
        item = self.tree.currentItem()
        if item is None:
            return ""
        value = item.data(0, _FOLDER_ROLE)
        return value or ""

    def _on_selection_changed(self, current: QTreeWidgetItem, _previous: QTreeWidgetItem) -> None:
        if current is None:
            return
        value = current.data(0, _FOLDER_ROLE)
        self.folder_selected.emit(value or "")
