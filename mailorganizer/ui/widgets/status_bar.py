"""Status bar showing connection state and mail counters."""

from __future__ import annotations

from PyQt6.QtWidgets import QLabel, QStatusBar


class AppStatusBar(QStatusBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.connection_label = QLabel("Status: ⚪ Nicht verbunden")
        self.count_label = QLabel("Mails: 0 | Neu: 0")
        self.addWidget(self.connection_label)
        self.addPermanentWidget(self.count_label)

    def set_connected(self, connected: bool) -> None:
        text = "Status: ✅ Verbunden" if connected else "Status: ⚪ Nicht verbunden"
        self.connection_label.setText(text)

    def set_counts(self, total: int, unread: int) -> None:
        self.count_label.setText(f"Mails: {total} | Neu: {unread}")
