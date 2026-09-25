"""Lightweight, dependency-free chart widgets drawn with QPainter (per plan section 16:
"Eigne UI-Components schreiben statt External Libs" instead of pulling in matplotlib).
"""

from __future__ import annotations

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import QWidget

_PALETTE = [
    QColor("#4C6EF5"),
    QColor("#F76707"),
    QColor("#2F9E44"),
    QColor("#E03131"),
    QColor("#AE3EC9"),
    QColor("#1098AD"),
    QColor("#F08C00"),
    QColor("#495057"),
]


def draw_pie_chart(painter: QPainter, rect: QRectF, data: dict[str, int], legend_font: QFont | None = None) -> None:
    """Draw a pie chart with a legend for `data` (label -> count) inside `rect`."""
    total = sum(data.values())
    if total <= 0:
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "Keine Daten")
        return

    chart_size = min(rect.width() * 0.55, rect.height())
    chart_rect = QRectF(rect.left(), rect.top(), chart_size, chart_size)

    start_angle = 90 * 16  # Qt angles are in 1/16th of a degree, starting at 3 o'clock, counter-clockwise
    painter.setPen(QPen(QColor("#ffffff"), 1))

    legend_x = chart_rect.right() + 20
    legend_y = rect.top()
    if legend_font:
        painter.setFont(legend_font)

    for i, (label, count) in enumerate(sorted(data.items(), key=lambda kv: -kv[1])):
        span_angle = -int(round(360 * 16 * count / total))
        color = _PALETTE[i % len(_PALETTE)]
        painter.setBrush(color)
        painter.drawPie(chart_rect, start_angle, span_angle)
        start_angle += span_angle

        painter.fillRect(int(legend_x), int(legend_y) + 2, 12, 12, color)
        pct = 100 * count / total
        painter.drawText(int(legend_x) + 18, int(legend_y) + 12, f"{label} ({count}, {pct:.0f}%)")
        legend_y += 20


def draw_bar_chart(painter: QPainter, rect: QRectF, data: dict[str, int]) -> None:
    """Draw a simple vertical bar chart for `data` (label -> value) inside `rect`."""
    if not data:
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "Keine Daten")
        return

    max_value = max(data.values()) or 1
    n = len(data)
    bar_area_height = rect.height() - 20
    bar_width = rect.width() / (n * 1.5)
    gap = bar_width * 0.5

    x = rect.left() + gap
    for i, (label, value) in enumerate(sorted(data.items())):
        bar_height = bar_area_height * (value / max_value)
        color = _PALETTE[i % len(_PALETTE)]
        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)
        bar_rect = QRectF(x, rect.top() + bar_area_height - bar_height, bar_width, bar_height)
        painter.drawRect(bar_rect)

        painter.setPen(QPen(QColor("#202020")))
        painter.drawText(
            QRectF(x - gap / 2, rect.top() + bar_area_height + 2, bar_width + gap, 18),
            Qt.AlignmentFlag.AlignHCenter,
            str(label),
        )
        painter.drawText(
            QRectF(x, rect.top() + bar_area_height - bar_height - 16, bar_width, 16),
            Qt.AlignmentFlag.AlignHCenter,
            str(value),
        )
        x += bar_width + gap


class PieChartWidget(QWidget):
    """On-screen pie chart widget; set_data(dict[label, count]) to update."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data: dict[str, int] = {}
        self.setMinimumHeight(220)

    def set_data(self, data: dict[str, int]) -> None:
        self._data = data
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt override)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        margin = 10
        rect = QRectF(margin, margin, self.width() - 2 * margin, self.height() - 2 * margin)
        draw_pie_chart(painter, rect, self._data)
        painter.end()


class BarChartWidget(QWidget):
    """On-screen bar chart widget; set_data(dict[label, value]) to update."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data: dict[str, int] = {}
        self.setMinimumHeight(180)

    def set_data(self, data: dict[str, int]) -> None:
        self._data = data
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt override)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        margin = 10
        rect = QRectF(margin, margin, self.width() - 2 * margin, self.height() - 2 * margin)
        draw_bar_chart(painter, rect, self._data)
        painter.end()
