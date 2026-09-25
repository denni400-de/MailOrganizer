"""Tab view for comparing multiple Ollama models on the same set of recent mails."""

from __future__ import annotations

import json

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from mailorganizer.models.mail import MailData
from mailorganizer.services.benchmark_service import BenchmarkReport, BenchmarkService
from mailorganizer.services.ollama_service import OllamaService
from mailorganizer.services.storage_service import StorageService
from mailorganizer.ui.workers import run_in_background


def _run_benchmark_task(ollama_url: str, mails: list[MailData], models: list[str]) -> BenchmarkReport:
    ollama_service = OllamaService(base_url=ollama_url)
    return BenchmarkService(ollama_service).run_benchmark(mails, models)


class BenchmarkView(QWidget):
    """Model-Benchmarking (plan 8.4): select models + a sample size, run, compare results.

    The Ollama URL is re-read from the user's saved Ollama config each run, so changes made
    in the Einstellungen tab take effect without recreating this view. Both model-listing and
    the benchmark run happen on a background thread so the UI stays responsive.
    """

    def __init__(self, storage: StorageService, parent=None):
        super().__init__(parent)
        self.storage = storage
        self.user_id: int | None = None

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Zu vergleichende Modelle:"))

        self.models_list = QListWidget()
        self.models_list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        layout.addWidget(self.models_list)

        refresh_row = QHBoxLayout()
        self.refresh_button = QPushButton("Modelle laden")
        self.refresh_button.clicked.connect(self._load_models)
        refresh_row.addWidget(self.refresh_button)
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

        self.run_button = QPushButton("Benchmark starten")
        self.run_button.clicked.connect(self._run_benchmark)
        layout.addWidget(self.run_button)

        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

    def set_user_id(self, user_id: int) -> None:
        self.user_id = user_id
        self._load_models()

    def _current_ollama_url(self) -> str:
        if self.user_id is None:
            return "http://localhost:11434"
        config = self.storage.get_ollama_config(self.user_id)
        return config.ollama_url if config else "http://localhost:11434"

    def _load_models(self) -> None:
        self.models_list.clear()
        self.refresh_button.setEnabled(False)
        self.status_label.setText("⏳ Lade Modelle …")
        run_in_background(
            OllamaService(base_url=self._current_ollama_url()).list_models,
            on_success=self._on_models_loaded,
            on_error=self._on_models_error,
        )

    def _on_models_loaded(self, models: list[str]) -> None:
        self.refresh_button.setEnabled(True)
        self.status_label.setText("")
        for model in models:
            item = QListWidgetItem(model)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.models_list.addItem(item)

    def _on_models_error(self, message: str) -> None:
        self.refresh_button.setEnabled(True)
        self.status_label.setText("")
        QMessageBox.warning(self, "Ollama nicht erreichbar", message)

    def _selected_models(self) -> list[str]:
        selected = []
        for i in range(self.models_list.count()):
            item = self.models_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                selected.append(item.text())
        return selected

    def _run_benchmark(self) -> None:
        if self.user_id is None:
            return
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

        self.run_button.setEnabled(False)
        self.status_label.setText(f"⏳ Benchmark läuft ({len(models)} Modell(e) × {len(mails)} Mail(s)) …")
        run_in_background(
            _run_benchmark_task,
            self._current_ollama_url(),
            mails,
            models,
            on_success=self._on_benchmark_done,
            on_error=self._on_benchmark_error,
        )

    def _on_benchmark_done(self, report: BenchmarkReport) -> None:
        self.run_button.setEnabled(True)
        self.status_label.setText("")
        self.results_table.setRowCount(0)
        for summary in report.summaries:
            row = self.results_table.rowCount()
            self.results_table.insertRow(row)
            self.results_table.setItem(row, 0, QTableWidgetItem(summary.model))
            self.results_table.setItem(row, 1, QTableWidgetItem(str(summary.mails_analyzed)))
            self.results_table.setItem(row, 2, QTableWidgetItem(str(summary.errors)))
            self.results_table.setItem(row, 3, QTableWidgetItem(f"{summary.avg_processing_time_ms:.0f}"))

    def _on_benchmark_error(self, message: str) -> None:
        self.run_button.setEnabled(True)
        self.status_label.setText("")
        QMessageBox.warning(self, "Benchmark fehlgeschlagen", message)
