"""Right-hand panel: mail header info, body preview and the AnalysisPanel."""

from __future__ import annotations

from PyQt6.QtWidgets import QLabel, QTextEdit, QVBoxLayout, QWidget

from mailorganizer.models.database import Mail
from mailorganizer.ui.widgets.analysis_panel import AnalysisPanel


class PreviewPanel(QWidget):
    """Shows sender/date/subject header plus the mail body and analysis results."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        self.sender_label = QLabel("Absender: -")
        self.date_label = QLabel("Datum: -")
        self.subject_label = QLabel("Betreff: -")
        self.subject_label.setWordWrap(True)

        self.body_view = QTextEdit()
        self.body_view.setReadOnly(True)

        self.analysis_panel = AnalysisPanel()

        layout.addWidget(self.sender_label)
        layout.addWidget(self.date_label)
        layout.addWidget(self.subject_label)
        layout.addWidget(self.body_view, stretch=1)
        layout.addWidget(self.analysis_panel)

    def clear(self) -> None:
        self.sender_label.setText("Absender: -")
        self.date_label.setText("Datum: -")
        self.subject_label.setText("Betreff: -")
        self.body_view.clear()
        self.analysis_panel.clear()

    def set_mail(self, mail: Mail | None) -> None:
        if mail is None:
            self.clear()
            return
        self.sender_label.setText(f"Absender: {mail.sender}")
        self.date_label.setText(f"Datum: {mail.received_at.strftime('%d.%m.%Y %H:%M')}")
        self.subject_label.setText(f"Betreff: {mail.subject}")
        self.body_view.setPlainText(mail.body or "")
        self.analysis_panel.set_analysis(mail.analysis)
