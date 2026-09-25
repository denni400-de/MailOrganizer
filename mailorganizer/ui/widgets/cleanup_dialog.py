"""Cleanup dialog implementing Workflow 3 (Mail-Cleanup) from the implementation plan."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QMessageBox,
    QProgressDialog,
    QSpinBox,
    QVBoxLayout,
)

from mailorganizer.services.cleanup_service import CleanupService, CleanupSummary
from mailorganizer.services.storage_service import StorageService
from mailorganizer.utils.exceptions import MailOrganizerError


class CleanupDialog(QDialog):
    """Options dialog: archive old mails, delete spam, remove duplicates, sort by importance."""

    def __init__(self, storage: StorageService, user_id: int, parent=None):
        super().__init__(parent)
        self.storage = storage
        self.user_id = user_id
        self.setWindowTitle("Mail-Cleanup")
        self.resize(380, 220)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Wähle die durchzuführenden Cleanup-Aktionen:"))

        self.archive_check = QCheckBox("Alte Mails archivieren, älter als:")
        self.archive_days_spin = QSpinBox()
        self.archive_days_spin.setRange(1, 3650)
        self.archive_days_spin.setValue(90)
        self.archive_days_spin.setSuffix(" Tage")

        self.spam_check = QCheckBox("Spam löschen")
        self.duplicates_check = QCheckBox("Doppelte löschen")
        self.sort_importance_check = QCheckBox("Danach nach Wichtigkeit sortiert anzeigen")

        layout.addWidget(self.archive_check)
        layout.addWidget(self.archive_days_spin)
        layout.addWidget(self.spam_check)
        layout.addWidget(self.duplicates_check)
        layout.addWidget(self.sort_importance_check)

        self.archive_check.toggled.connect(self.archive_days_spin.setEnabled)
        self.archive_days_spin.setEnabled(False)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._run_cleanup)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.sort_by_importance = False
        self._summary: CleanupSummary | None = None

    def _run_cleanup(self) -> None:
        if not (self.archive_check.isChecked() or self.spam_check.isChecked() or self.duplicates_check.isChecked()):
            QMessageBox.information(self, "Hinweis", "Bitte mindestens eine Aktion auswählen.")
            return

        confirm = QMessageBox.question(
            self,
            "Bestätigung",
            "Ausgewählte Cleanup-Aktionen jetzt ausführen? Gelöschte Mails können nicht wiederhergestellt werden.",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        progress = QProgressDialog("Cleanup wird durchgeführt...", None, 0, 0, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setCancelButton(None)
        progress.show()

        service = CleanupService(self.storage)
        try:
            self._summary = service.run(
                user_id=self.user_id,
                archive_older_than_days=self.archive_days_spin.value() if self.archive_check.isChecked() else None,
                delete_spam=self.spam_check.isChecked(),
                delete_duplicates=self.duplicates_check.isChecked(),
            )
        except MailOrganizerError as exc:
            progress.close()
            QMessageBox.critical(self, "Fehler", str(exc))
            return
        finally:
            progress.close()

        self.sort_by_importance = self.sort_importance_check.isChecked()

        QMessageBox.information(
            self,
            "Cleanup abgeschlossen",
            (
                f"Archiviert: {self._summary.archived}\n"
                f"Spam gelöscht: {self._summary.spam_deleted}\n"
                f"Duplikate gelöscht: {self._summary.duplicates_deleted}"
            ),
        )
        self.accept()

    def summary(self) -> CleanupSummary | None:
        return self._summary
