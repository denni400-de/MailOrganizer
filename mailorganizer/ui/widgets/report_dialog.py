"""Weekly report dialog with a category pie chart, importance bar chart, top senders,
suggested cleanup actions, and PDF export via Qt's built-in QPdfWriter (no extra dependency).
"""

from __future__ import annotations

from PyQt6.QtCore import QRectF
from PyQt6.QtGui import QFont, QPageSize, QPainter
from PyQt6.QtPrintSupport import QPrinter
from PyQt6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from mailorganizer.services.report_service import ReportData, ReportService
from mailorganizer.services.storage_service import StorageService
from mailorganizer.ui.widgets.charts import BarChartWidget, PieChartWidget, draw_bar_chart, draw_pie_chart


class ReportDialog(QDialog):
    """Displays the weekly report and offers a "Export als PDF" button."""

    def __init__(self, storage: StorageService, user_id: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Wöchentlicher Bericht")
        self.resize(640, 640)

        self.report_data = ReportService(storage).generate_weekly_report(user_id)

        outer_layout = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)

        period_label = QLabel(
            f"Zeitraum: {self.report_data.period_start.strftime('%d.%m.%Y')} – "
            f"{self.report_data.period_end.strftime('%d.%m.%Y')} "
            f"({self.report_data.total_mails} Mails)"
        )
        header_font = QFont()
        header_font.setBold(True)
        period_label.setFont(header_font)
        layout.addWidget(period_label)

        layout.addWidget(QLabel("Top Absender:"))
        senders_list = QListWidget()
        for sender, count in self.report_data.top_senders:
            senders_list.addItem(f"{sender} — {count} Mail(s)")
        senders_list.setMaximumHeight(120)
        layout.addWidget(senders_list)

        layout.addWidget(QLabel("Kategorie-Statistik:"))
        self.pie_chart = PieChartWidget()
        self.pie_chart.set_data(self.report_data.category_counts)
        layout.addWidget(self.pie_chart)

        layout.addWidget(QLabel("Wichtigkeits-Verteilung:"))
        self.bar_chart = BarChartWidget()
        self.bar_chart.set_data({str(k): v for k, v in self.report_data.importance_distribution.items()})
        layout.addWidget(self.bar_chart)

        layout.addWidget(QLabel("Vorgeschlagene Aufräum-Aktionen:"))
        suggestions_list = QListWidget()
        for suggestion in self.report_data.suggested_actions:
            suggestions_list.addItem(suggestion)
        suggestions_list.setMaximumHeight(120)
        layout.addWidget(suggestions_list)

        scroll.setWidget(content)
        outer_layout.addWidget(scroll)

        button_row = QHBoxLayout()
        export_button = QPushButton("Als PDF exportieren")
        export_button.clicked.connect(self._export_pdf)
        close_button = QPushButton("Schließen")
        close_button.clicked.connect(self.accept)
        button_row.addWidget(export_button)
        button_row.addStretch(1)
        button_row.addWidget(close_button)
        outer_layout.addLayout(button_row)

    def _export_pdf(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Bericht als PDF speichern", "mailorganizer_bericht.pdf", "PDF (*.pdf)")
        if not path:
            return
        try:
            export_report_pdf(self.report_data, path)
            QMessageBox.information(self, "Export erfolgreich", f"Bericht gespeichert unter:\n{path}")
        except OSError as exc:
            QMessageBox.critical(self, "Export fehlgeschlagen", str(exc))


def export_report_pdf(report: ReportData, path: str) -> None:
    """Render the report (header, top senders, charts, suggestions) to a PDF file via QPrinter."""
    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    printer.setOutputFileName(path)

    painter = QPainter(printer)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    page_rect = printer.pageRect(QPrinter.Unit.DevicePixel)
    margin = 40
    x = page_rect.left() + margin
    y = page_rect.top() + margin
    width = page_rect.width() - 2 * margin

    title_font = QFont()
    title_font.setPointSize(16)
    title_font.setBold(True)
    painter.setFont(title_font)
    painter.drawText(int(x), int(y), "Mail Organizer – Wöchentlicher Bericht")
    y += 30

    normal_font = QFont()
    normal_font.setPointSize(10)
    painter.setFont(normal_font)
    painter.drawText(
        int(x),
        int(y),
        f"Zeitraum: {report.period_start.strftime('%d.%m.%Y')} – {report.period_end.strftime('%d.%m.%Y')} "
        f"({report.total_mails} Mails)",
    )
    y += 30

    bold_font = QFont()
    bold_font.setBold(True)
    painter.setFont(bold_font)
    painter.drawText(int(x), int(y), "Top Absender:")
    y += 20
    painter.setFont(normal_font)
    for sender, count in report.top_senders:
        painter.drawText(int(x) + 10, int(y), f"• {sender} — {count} Mail(s)")
        y += 16
    y += 20

    painter.setFont(bold_font)
    painter.drawText(int(x), int(y), "Kategorie-Statistik:")
    y += 10
    chart_rect = QRectF(x, y, width, 200)
    draw_pie_chart(painter, chart_rect, report.category_counts)
    y += 220

    painter.setFont(bold_font)
    painter.drawText(int(x), int(y), "Wichtigkeits-Verteilung:")
    y += 10
    bar_rect = QRectF(x, y, min(width, 300), 160)
    draw_bar_chart(painter, bar_rect, {str(k): v for k, v in report.importance_distribution.items()})
    y += 190

    painter.setFont(bold_font)
    painter.drawText(int(x), int(y), "Vorgeschlagene Aufräum-Aktionen:")
    y += 20
    painter.setFont(normal_font)
    for suggestion in report.suggested_actions:
        painter.drawText(int(x) + 10, int(y), f"• {suggestion}")
        y += 16

    painter.end()
