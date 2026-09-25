"""Displays the LLM analysis result for the currently previewed mail."""

from __future__ import annotations

from PyQt6.QtWidgets import QFormLayout, QGroupBox, QLabel

from mailorganizer.models.database import MailAnalysis

_STARS = {1: "⭐", 2: "⭐⭐", 3: "⭐⭐⭐", 4: "⭐⭐⭐⭐", 5: "⭐⭐⭐⭐⭐"}


class AnalysisPanel(QGroupBox):
    """Group box showing Kategorie / Wichtigkeit / Sentiment / Aktion."""

    def __init__(self, parent=None):
        super().__init__("Analyse-Ergebnisse", parent)
        layout = QFormLayout(self)

        self.category_label = QLabel("-")
        self.importance_label = QLabel("-")
        self.sentiment_label = QLabel("-")
        self.action_label = QLabel("-")
        self.summary_label = QLabel("-")
        self.summary_label.setWordWrap(True)

        layout.addRow("Kategorie:", self.category_label)
        layout.addRow("Wichtigkeit:", self.importance_label)
        layout.addRow("Sentiment:", self.sentiment_label)
        layout.addRow("Aktion:", self.action_label)
        layout.addRow("Zusammenfassung:", self.summary_label)

    def clear(self) -> None:
        for label in (
            self.category_label,
            self.importance_label,
            self.sentiment_label,
            self.action_label,
            self.summary_label,
        ):
            label.setText("-")

    def set_analysis(self, analysis: MailAnalysis | None) -> None:
        if analysis is None:
            self.clear()
            return
        self.category_label.setText(analysis.category or "-")
        self.importance_label.setText(_STARS.get(analysis.importance_score or 0, "-"))
        self.sentiment_label.setText(analysis.sentiment or "-")
        self.action_label.setText(analysis.recommended_action or "-")
        self.summary_label.setText(analysis.summary or "-")
