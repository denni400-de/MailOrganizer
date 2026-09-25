"""Chat-Tab: Konversation mit der KI (läuft im Hintergrund, damit die UI nicht einfriert),
plus eine Trefferliste, die gefundene Mails aus Tool-Aufrufen anzeigt und anklickbar macht.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from mailorganizer.services.chat_service import ChatMessage, ChatService, ChatTools, ChatTurnResult
from mailorganizer.services.ollama_service import OllamaService
from mailorganizer.services.storage_service import StorageService
from mailorganizer.ui.workers import run_in_background

_LIST_TOOLS = {"list_mails", "search_mails"}


def _run_chat_task(
    storage: StorageService,
    ollama_url: str,
    model: str,
    user_id: int,
    temperature: float,
    max_tokens: int,
    history: list[ChatMessage],
    text: str,
) -> ChatTurnResult:
    service = ChatService(
        storage=storage,
        ollama_service=OllamaService(base_url=ollama_url),
        model=model,
        user_id=user_id,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return service.send_message(history, text)


class ChatView(QWidget):
    """Chat links, Trefferliste + Vorschau rechts. Läuft im Hintergrund-Thread."""

    def __init__(self, storage: StorageService, parent=None):
        super().__init__(parent)
        self.storage = storage
        self.user_id: int | None = None
        self.history: list[ChatMessage] = []
        self._result_mail_ids: list[int] = []
        self._preview_request_id = 0

        outer_layout = QVBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        chat_side = QWidget()
        chat_layout = QVBoxLayout(chat_side)
        chat_layout.setContentsMargins(0, 0, 0, 0)

        self.history_view = QTextEdit()
        self.history_view.setReadOnly(True)
        chat_layout.addWidget(self.history_view, stretch=1)

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
        chat_layout.addLayout(input_row)

        self.status_label = QLabel("Hinweis: Die KI kann Mails suchen, zusammenfassen und auf Zuruf archivieren.")
        self.status_label.setEnabled(False)
        chat_layout.addWidget(self.status_label)

        splitter.addWidget(chat_side)

        results_side = QWidget()
        results_layout = QVBoxLayout(results_side)
        results_layout.setContentsMargins(0, 0, 0, 0)
        results_layout.addWidget(QLabel("Gefundene Mails:"))

        self.results_table = QTableWidget(0, 3)
        self.results_table.setHorizontalHeaderLabels(["Von", "Betreff", "Datum"])
        self.results_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.results_table.setSelectionBehavior(self.results_table.SelectionBehavior.SelectRows)
        self.results_table.setEditTriggers(self.results_table.EditTrigger.NoEditTriggers)
        self.results_table.itemSelectionChanged.connect(self._on_result_selected)
        results_layout.addWidget(self.results_table, stretch=1)

        results_layout.addWidget(QLabel("Vorschau:"))
        self.preview_view = QTextEdit()
        self.preview_view.setReadOnly(True)
        results_layout.addWidget(self.preview_view, stretch=1)

        splitter.addWidget(results_side)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 1)

        outer_layout.addWidget(splitter)

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
        self.input_edit.setEnabled(False)
        self.send_button.setEnabled(False)
        self._append(f"<b>Du:</b> {_escape(text)}")
        self.status_label.setText("⏳ Die KI denkt nach …")

        run_in_background(
            _run_chat_task,
            self.storage,
            ollama_config.ollama_url,
            ollama_config.ollama_model,
            self.user_id,
            min(ollama_config.temperature, 0.5),
            ollama_config.max_tokens,
            list(self.history),
            text,
            on_success=lambda result: self._on_reply(text, result),
            on_error=self._on_error,
        )

    def _on_reply(self, user_text: str, result: ChatTurnResult) -> None:
        self.input_edit.setEnabled(True)
        self.send_button.setEnabled(True)
        self.status_label.setText("Hinweis: Die KI kann Mails suchen, zusammenfassen und auf Zuruf archivieren.")

        collected_mails: list[dict] = []
        seen_ids: set = set()
        for call in result.tool_calls:
            self._append(
                f"<i>🔧 {_escape(call.tool)}({_escape(str(call.args))}) → "
                f"{_escape(call.result_summary[:200])}{'…' if len(call.result_summary) > 200 else ''}</i>"
            )
            if call.tool in _LIST_TOOLS and isinstance(call.result, list):
                # A turn can make several list-returning tool calls (e.g. list_mails then
                # search_mails) — accumulate all of them instead of letting the last call's
                # results silently replace the earlier ones in the table.
                for mail in call.result:
                    mail_id = mail.get("id")
                    if mail_id in seen_ids:
                        continue
                    seen_ids.add(mail_id)
                    collected_mails.append(mail)

        if collected_mails:
            self._show_results(collected_mails)

        self._append(f"<b>Assistent:</b> {_escape(result.final_answer)}")

        self.history.append(ChatMessage(role="user", content=user_text))
        self.history.append(ChatMessage(role="assistant", content=result.final_answer))

    def _on_error(self, message: str) -> None:
        self.input_edit.setEnabled(True)
        self.send_button.setEnabled(True)
        self.status_label.setText("Hinweis: Die KI kann Mails suchen, zusammenfassen und auf Zuruf archivieren.")
        self._append(f"<i>Fehler: {_escape(message)}</i>")

    def _show_results(self, mails: list[dict]) -> None:
        self.results_table.setRowCount(0)
        self._result_mail_ids = []
        for mail in mails:
            row = self.results_table.rowCount()
            self.results_table.insertRow(row)
            self.results_table.setItem(row, 0, QTableWidgetItem(str(mail.get("sender", ""))))
            self.results_table.setItem(row, 1, QTableWidgetItem(str(mail.get("subject", ""))))
            self.results_table.setItem(row, 2, QTableWidgetItem(str(mail.get("date", ""))))
            self._result_mail_ids.append(mail.get("id"))
        self.preview_view.clear()

    def _on_result_selected(self) -> None:
        if self.user_id is None:
            return
        rows = self.results_table.selectionModel().selectedRows()
        if not rows:
            return
        row = rows[0].row()
        if not (0 <= row < len(self._result_mail_ids)):
            return
        mail_id = self._result_mail_ids[row]
        if mail_id is None:
            return

        self._preview_request_id += 1
        request_id = self._preview_request_id
        self.preview_view.setPlainText("⏳ Lade …")
        run_in_background(
            ChatTools(self.storage, self.user_id).get_mail,
            mail_id,
            on_success=lambda mail: self._on_preview_loaded(request_id, mail),
            on_error=lambda msg: self._on_preview_loaded(request_id, None),
        )

    def _on_preview_loaded(self, request_id: int, mail: dict | None) -> None:
        if request_id != self._preview_request_id:
            return  # a newer row was selected while this lookup was still running — discard
        if mail is None:
            self.preview_view.setPlainText("(nicht mehr verfügbar)")
            return
        self.preview_view.setPlainText(
            f"Von: {mail.get('sender', '')}\n"
            f"Betreff: {mail.get('subject', '')}\n"
            f"Datum: {mail.get('date', '')}\n"
            f"Kategorie: {mail.get('category') or '-'}\n\n"
            f"{mail.get('body', '')}"
        )


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
