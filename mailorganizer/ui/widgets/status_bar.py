"""Status bar showing connection state, mail counters, and a busy indicator for
background operations (Sync, Analyse, Ordner laden, ...) so the app never looks frozen.
"""

from __future__ import annotations

from PyQt6.QtWidgets import QLabel, QProgressBar, QStatusBar


class AppStatusBar(QStatusBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.connection_label = QLabel("Status: ⚪ Nicht verbunden")
        self.busy_label = QLabel("")
        self.busy_bar = QProgressBar()
        self.busy_bar.setMaximumWidth(160)
        self.busy_bar.setMaximumHeight(14)
        self.busy_bar.setTextVisible(False)
        self.busy_bar.setRange(0, 0)  # indeterminate by default
        self.busy_bar.hide()
        self.count_label = QLabel("Mails: 0 | Neu: 0")

        self.addWidget(self.connection_label)
        self.addWidget(self.busy_label)
        self.addWidget(self.busy_bar)
        self.addPermanentWidget(self.count_label)

    def set_connected(self, connected: bool) -> None:
        text = "Status: ✅ Verbunden" if connected else "Status: ⚪ Nicht verbunden"
        self.connection_label.setText(text)

    def set_counts(self, total: int, unread: int) -> None:
        self.count_label.setText(f"Mails: {total} | Neu: {unread}")

    def start_busy(self, text: str) -> None:
        """Show an indeterminate progress bar with a status message."""
        self.busy_label.setText(text)
        self.busy_bar.setRange(0, 0)
        self.busy_bar.show()

    def set_busy_progress(self, current: int, total: int) -> None:
        """Switch the busy bar to determinate mode and set its position."""
        if total > 0:
            self.busy_bar.setRange(0, total)
            self.busy_bar.setValue(current)
        else:
            self.busy_bar.setRange(0, 0)

    def stop_busy(self) -> None:
        self.busy_label.setText("")
        self.busy_bar.hide()
