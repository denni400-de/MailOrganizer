"""Chat-Tab: Konversation mit der KI, die per Tool-Calling im Postfach suchen, Mails
zusammenfassen oder aufräumen kann.
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from mailorganizer.services.chat_service import ChatMessage, ChatService
from mailorganizer.services.ollama_service import OllamaService
from mailorganizer.services.storage_service import StorageService
from mailorganizer.utils.exceptions import MailOrganizerError


class ChatView(QWidget):
    """Chat-Fenster: Verlauf oben, Eingabezeile unten. Führt bei Bedarf Tool-Aufrufe aus."""

    def __init__(self, storage: StorageService, parent=None):
        super().__init__(parent)
        self.storage = storage
        self.user_id: int | None = None
        self.history: list[ChatMessage] = []

        layout = QVBoxLayout(self)

        self.history_view = QTextEdit()
        self.history_view.setReadOnly(True)
        layout.addWidget(self.history_view, stretch=1)

        input_row = QHBoxLayout()
        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText(
            "z. B. 'Zeig mir alle Rechnungen von dieser Woche' oder 'Fasse meine ungelesenen Mails zusammen'"
        )
        self.input_edit.returnPressed.connect(self._send)
        self.send_button = QPushButton("Senden")
        self.send_button.clicked.connect(self._send)
        input_row.addWidget(self.input_edit, stretch=1)
        input_row.addWidget(self.send_button)
        layout.addLayout(input_row)

        hint = QLabel("Hinweis: Die KI kann Mails suchen, zusammenfassen und auf Zuruf archivieren.")
        hint.setEnabled(False)
        layout.addWidget(hint)

    def set_user_id(self, user_id: int) -> None:
        self.user_id = user_id

    def _append(self, html: str) -> None:
        self.history_view.append(html)

    def _send(self) -> None:
        if self.user_id is None:
            QMessageBox.information(self, "Hinweis", "Bitte zuerst ein Mail-Konto einrichten.")
            return
        text = self.input_edit.text().strip()
        if not text:
            return

        ollama_config = self.storage.get_ollama_config(self.user_id)
        if ollama_config is None:
            QMessageBox.information(self, "Hinweis", "Bitte zuerst Ollama in den Einstellungen konfigurieren.")
            return

        self.input_edit.clear()
        self._append(f"<b>Du:</b> {_escape(text)}")
        self.history_view.repaint()
        QApplication.processEvents()

        service = ChatService(
            storage=self.storage,
            ollama_service=OllamaService(base_url=ollama_config.ollama_url),
            model=ollama_config.ollama_model,
            user_id=self.user_id,
            temperature=min(ollama_config.temperature, 0.5),
            max_tokens=ollama_config.max_tokens,
        )

        try:
            result = service.send_message(self.history, text)
        except MailOrganizerError as exc:
            self._append(f"<i>Fehler: {_escape(str(exc))}</i>")
            return

        for call in result.tool_calls:
            self._append(
                f"<i>🔧 {_escape(call.tool)}({_escape(str(call.args))}) → "
                f"{_escape(call.result_summary[:200])}{'…' if len(call.result_summary) > 200 else ''}</i>"
            )

        self._append(f"<b>Assistent:</b> {_escape(result.final_answer)}")

        self.history.append(ChatMessage(role="user", content=text))
        self.history.append(ChatMessage(role="assistant", content=result.final_answer))


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
