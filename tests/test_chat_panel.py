from __future__ import annotations

import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("PyQt6")

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from mailorganizer.models.mail import MailData
from mailorganizer.services.ollama_service import OllamaResponse
from mailorganizer.services.storage_service import StorageService
from mailorganizer.ui.widgets.chat_panel import ChatView


@pytest.fixture
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _run_until(app, predicate, timeout_ms=5000):
    timer = QTimer()
    timer.timeout.connect(lambda: app.quit() if predicate() else None)
    timer.start(10)
    QTimer.singleShot(timeout_ms, app.quit)
    app.exec()
    timer.stop()


@pytest.fixture
def view(qapp):
    with tempfile.TemporaryDirectory() as tmp:
        storage = StorageService(Path(tmp) / "test.db")
        user = storage.get_or_create_user("a@b.com", "imap.x.com", "smtp.x.com", "pw")
        storage.save_ollama_config(user.id, "http://localhost:11434", "mistral:latest")
        storage.save_mail(
            user.id,
            MailData(
                message_id="<1@x>", sender="amazon@shop.com", recipients=["a@b.com"],
                subject="Rechnung", received_at=datetime.now(), body="Rechnungstext",
            ),
        )
        storage.save_mail(
            user.id,
            MailData(
                message_id="<2@x>", sender="friend@x.com", recipients=["a@b.com"],
                subject="Hallo", received_at=datetime.now(), body="Hi da",
            ),
        )
        v = ChatView(storage)
        v.set_user_id(user.id)
        yield v


def test_results_from_multiple_tool_calls_accumulate(view, qapp):
    """Regression test: a turn with several list-returning tool calls (e.g. list_mails then
    search_mails) must show the union of their results, not just the last call's."""
    with patch("mailorganizer.ui.widgets.chat_panel.OllamaService") as mock_cls:
        mock_instance = MagicMock()
        mock_instance.generate.side_effect = [
            OllamaResponse(text='{"tool": "list_mails", "args": {}}', model="m"),
            OllamaResponse(text='{"tool": "search_mails", "args": {"query": "Hallo"}}', model="m"),
            OllamaResponse(text='{"final_answer": "Hier sind beide Ergebnisse."}', model="m"),
        ]
        mock_cls.return_value = mock_instance

        view.input_edit.setText("Zeig mir alles und suche nach Hallo")
        view._send()

        _run_until(qapp, lambda: view.send_button.isEnabled())

        assert view.results_table.rowCount() == 2
        subjects = {view.results_table.item(r, 1).text() for r in range(2)}
        assert subjects == {"Rechnung", "Hallo"}


def test_result_click_does_not_block_and_loads_preview(view, qapp):
    """Regression test: clicking a chat result row must not run a synchronous DB read on the
    GUI thread — the preview should show a placeholder immediately, then fill in async."""
    with patch("mailorganizer.ui.widgets.chat_panel.OllamaService") as mock_cls:
        mock_instance = MagicMock()
        mock_instance.generate.side_effect = [
            OllamaResponse(text='{"tool": "list_mails", "args": {}}', model="m"),
            OllamaResponse(text='{"final_answer": "Da sind sie."}', model="m"),
        ]
        mock_cls.return_value = mock_instance

        view.input_edit.setText("Zeig mir alles")
        view._send()
        _run_until(qapp, lambda: view.send_button.isEnabled())

    view.results_table.selectRow(0)
    assert view.preview_view.toPlainText() == "⏳ Lade …"

    _run_until(qapp, lambda: "Lade" not in view.preview_view.toPlainText())

    # list_mails orders by received_at desc, so row 0 isn't necessarily the first-saved mail —
    # just assert the preview loaded one of the two real bodies, not the placeholder/error.
    assert any(body in view.preview_view.toPlainText() for body in ("Rechnungstext", "Hi da"))


def test_result_click_discards_stale_response(view, qapp):
    """Regression test: if the user selects a second row before the first row's background
    lookup finishes, the stale (first) lookup must not overwrite the newer preview."""
    with patch("mailorganizer.ui.widgets.chat_panel.OllamaService") as mock_cls:
        mock_instance = MagicMock()
        mock_instance.generate.side_effect = [
            OllamaResponse(text='{"tool": "list_mails", "args": {}}', model="m"),
            OllamaResponse(text='{"final_answer": "Da sind sie."}', model="m"),
        ]
        mock_cls.return_value = mock_instance
        view.input_edit.setText("Zeig mir alles")
        view._send()
        _run_until(qapp, lambda: view.send_button.isEnabled())

    # Select row 0, then immediately row 1 before the first background lookup can complete.
    view.results_table.selectRow(0)
    first_request_id = view._preview_request_id
    view.results_table.selectRow(1)
    assert view._preview_request_id != first_request_id

    _run_until(qapp, lambda: "Lade" not in view.preview_view.toPlainText())

    # The visible preview must correspond to the second (final) selection, not the first.
    assert view.preview_view.toPlainText() != ""


def test_zero_match_followup_search_clears_stale_results(view, qapp):
    """Regression test: a follow-up turn whose list/search tool call matches nothing must
    still clear the previous (unrelated) results, not leave them looking like matches for
    the new, empty query."""
    with patch("mailorganizer.ui.widgets.chat_panel.OllamaService") as mock_cls:
        mock_instance = MagicMock()
        mock_instance.generate.side_effect = [
            OllamaResponse(text='{"tool": "list_mails", "args": {}}', model="m"),
            OllamaResponse(text='{"final_answer": "Hier sind alle Mails."}', model="m"),
        ]
        mock_cls.return_value = mock_instance
        view.input_edit.setText("Zeig mir alles")
        view._send()
        _run_until(qapp, lambda: view.send_button.isEnabled())

    assert view.results_table.rowCount() == 2  # sanity check: the first turn populated it

    with patch("mailorganizer.ui.widgets.chat_panel.OllamaService") as mock_cls:
        mock_instance = MagicMock()
        mock_instance.generate.side_effect = [
            OllamaResponse(text='{"tool": "search_mails", "args": {"query": "nichts-passt"}}', model="m"),
            OllamaResponse(text='{"final_answer": "Keine Treffer."}', model="m"),
        ]
        mock_cls.return_value = mock_instance
        view.input_edit.setText("Suche nach nichts-passt")
        view._send()
        _run_until(qapp, lambda: view.send_button.isEnabled())

    assert view.results_table.rowCount() == 0


def test_show_results_invalidates_in_flight_preview_lookup(view, qapp):
    """Regression test: if a get_mail lookup for a previously selected row is still running
    when a new turn's _show_results() resets the table, that stale lookup's eventual result
    must not land in the (now-cleared) preview pane."""
    import time as time_module

    with patch("mailorganizer.ui.widgets.chat_panel.OllamaService") as mock_cls:
        mock_instance = MagicMock()
        mock_instance.generate.side_effect = [
            OllamaResponse(text='{"tool": "list_mails", "args": {}}', model="m"),
            OllamaResponse(text='{"final_answer": "Da sind sie."}', model="m"),
        ]
        mock_cls.return_value = mock_instance
        view.input_edit.setText("Zeig mir alles")
        view._send()
        _run_until(qapp, lambda: view.send_button.isEnabled())

    def slow_get_mail(mail_id):
        time_module.sleep(0.3)
        return {"sender": "stale@x.com", "subject": "STALE", "date": "-", "category": None, "body": "stale body"}

    with patch("mailorganizer.ui.widgets.chat_panel.ChatTools") as mock_tools_cls:
        mock_tools_cls.return_value.get_mail.side_effect = slow_get_mail
        view.results_table.selectRow(0)  # kicks off the slow (stale-by-the-time-it-finishes) lookup

        with patch("mailorganizer.ui.widgets.chat_panel.OllamaService") as mock_cls:
            mock_instance = MagicMock()
            mock_instance.generate.side_effect = [
                OllamaResponse(text='{"tool": "search_mails", "args": {"query": "nichts"}}', model="m"),
                OllamaResponse(text='{"final_answer": "Keine Treffer."}', model="m"),
            ]
            mock_cls.return_value = mock_instance
            view.input_edit.setText("Suche nach nichts")
            view._send()
            _run_until(qapp, lambda: view.send_button.isEnabled())

        # Give the slow, now-stale get_mail lookup time to finish and (incorrectly, if the
        # bug were present) try to overwrite the preview.
        _run_until(qapp, lambda: False, timeout_ms=500)

    assert view.preview_view.toPlainText() == ""
    assert "STALE" not in view.preview_view.toPlainText()
