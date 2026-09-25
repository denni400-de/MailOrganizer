"""Dialog for comparing multiple Ollama models on the same set of recent mails."""

from __future__ import annotations

import json

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from mailorganizer.models.mail import MailData
from mailorganizer.services.benchmark_service import BenchmarkService
from mailorganizer.services.ollama_service import OllamaService
from mailorganizer.services.storage_service import StorageService
from mailorganizer.utils.exceptions import MailOrganizerError


class BenchmarkDialog(QDialog):
    """Model-Benchmarking (plan 8.4): select models + a sample size, run, compare results."""

    def __init__(self, storage: StorageService, user_id: int, ollama_url: str, parent=None):
        super().__init__(parent)
        self.storage = storage
        self.user_id = user_id
        self.ollama_url = ollama_url
        self.setWindowTitle("Ollama-Model-Benchmarking")
        self.resize(560, 480)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Zu vergleichende Modelle:"))

        self.models_list = QListWidget()
        self.models_list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        layout.addWidget(self.models_list)

        refresh_row = QHBoxLayout()
        refresh_button = QPushButton("Modelle laden")
        refresh_button.clicked.connect(self._load_models)
        refresh_row.addWidget(refresh_button)
        refresh_row.addStretch(1)
        layout.addLayout(refresh_row)

        sample_row = QHBoxLayout()
        sample_row.addWidget(QLabel("Anzahl Mails (aus Verlauf):"))
        self.sample_spin = QSpinBox()
        self.sample_spin.setRange(1, 50)
        self.sample_spin.setValue(5)
        sample_row.addWidget(self.sample_spin)
        sample_row.addStretch(1)
        layout.addLayout(sample_row)

        self.results_table = QTableWidget(0, 4)
        self.results_table.setHorizontalHeaderLabels(["Modell", "Analysiert", "Fehler", "Ø Zeit (ms)"])
        self.results_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.results_table)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        self.run_button = QPushButton("Benchmark starten")
        self.run_button.clicked.connect(self._run_benchmark)
        buttons.addButton(self.run_button, QDialogButtonBox.ButtonRole.ActionRole)
        layout.addWidget(buttons)

        self._load_models()

    def _load_models(self) -> None:
        self.models_list.clear()
        try:
            models = OllamaService(base_url=self.ollama_url).list_models()
        except MailOrganizerError as exc:
            QMessageBox.warning(self, "Ollama nicht erreichbar", str(exc))
            return
        for model in models:
            item = QListWidgetItem(model)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.models_list.addItem(item)

    def _selected_models(self) -> list[str]:
        selected = []
        for i in range(self.models_list.count()):
            item = self.models_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                selected.append(item.text())
        return selected

    def _run_benchmark(self) -> None:
        models = self._selected_models()
        if not models:
            QMessageBox.information(self, "Hinweis", "Bitte mindestens ein Modell auswählen.")
            return

        db_mails = self.storage.list_mails(self.user_id, limit=self.sample_spin.value())
        if not db_mails:
            QMessageBox.information(self, "Hinweis", "Keine Mails im Verlauf gefunden.")
            return

        mails = [
            MailData(
                message_id=m.message_id,
                sender=m.sender,
                recipients=json.loads(m.recipients or "[]"),
                subject=m.subject,
                received_at=m.received_at,
                body=m.body or "",
                html_body=m.html_body or "",
            )
            for m in db_mails
        ]

        progress = QProgressDialog("Benchmark läuft...", None, 0, 0, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setCancelButton(None)
        progress.show()

        try:
            ollama_service = OllamaService(base_url=self.ollama_url)
            report = BenchmarkService(ollama_service).run_benchmark(mails, models)
        finally:
            progress.close()

        self.results_table.setRowCount(0)
        for summary in report.summaries:
            row = self.results_table.rowCount()
            self.results_table.insertRow(row)
            self.results_table.setItem(row, 0, QTableWidgetItem(summary.model))
            self.results_table.setItem(row, 1, QTableWidgetItem(str(summary.mails_analyzed)))
            self.results_table.setItem(row, 2, QTableWidgetItem(str(summary.errors)))
            self.results_table.setItem(row, 3, QTableWidgetItem(f"{summary.avg_processing_time_ms:.0f}"))
