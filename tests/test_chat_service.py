from __future__ import annotations

import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from mailorganizer.models.mail import MailData
from mailorganizer.services.chat_service import ChatService, ChatTools
from mailorganizer.services.ollama_service import OllamaResponse
from mailorganizer.services.storage_service import StorageService


@pytest.fixture
def storage():
    with tempfile.TemporaryDirectory() as tmp:
        yield StorageService(Path(tmp) / "test.db")


@pytest.fixture
def user_id(storage):
    user = storage.get_or_create_user("a@b.com", "imap.x.com", "smtp.x.com", "encpass")
    return user.id


def make_mail(message_id, **overrides) -> MailData:
    defaults = dict(
        message_id=message_id,
        sender="s@x.com",
        recipients=["a@b.com"],
        subject="Subject",
        received_at=datetime.now(),
        body="body text",
    )
    defaults.update(overrides)
    return MailData(**defaults)


# -- ChatTools ---------------------------------------------------------


def test_tools_search_mails_matches_subject(storage, user_id):
    storage.save_mail(user_id, make_mail("<1@x>", subject="Rechnung Januar"))
    storage.save_mail(user_id, make_mail("<2@x>", subject="Hallo"))

    tools = ChatTools(storage, user_id)
    results = tools.search_mails("Rechnung")

    assert len(results) == 1
    assert results[0]["subject"] == "Rechnung Januar"


def test_tools_get_mail_returns_body(storage, user_id):
    mail = storage.save_mail(user_id, make_mail("<1@x>", body="Geheimer Inhalt"))
    tools = ChatTools(storage, user_id)

    result = tools.get_mail(mail.id)

    assert result is not None
    assert "Geheimer Inhalt" in result["body"]


def test_tools_get_mail_unknown_id_returns_none(storage, user_id):
    tools = ChatTools(storage, user_id)
    assert tools.get_mail(9999) is None


def test_tools_archive_mails(storage, user_id):
    mail = storage.save_mail(user_id, make_mail("<1@x>"))
    tools = ChatTools(storage, user_id)

    count = tools.archive_mails([mail.id])

    assert count == 1
    assert storage.list_mails(user_id) == []


def test_tools_list_mails_unread_only(storage, user_id):
    storage.save_mail(user_id, make_mail("<1@x>", is_read=True))
    storage.save_mail(user_id, make_mail("<2@x>", is_read=False))

    tools = ChatTools(storage, user_id)
    results = tools.list_mails(unread_only=True)

    assert len(results) == 1
    assert results[0]["is_read"] is False


# -- ChatService ---------------------------------------------------------


def test_send_message_final_answer_without_tools(storage, user_id):
    ollama = MagicMock()
    ollama.generate.return_value = OllamaResponse(text='{"final_answer": "Hallo!"}', model="m")

    service = ChatService(storage, ollama, "mistral:latest", user_id)
    result = service.send_message([], "Hi")

    assert result.final_answer == "Hallo!"
    assert result.tool_calls == []


def test_send_message_runs_tool_then_answers(storage, user_id):
    storage.save_mail(user_id, make_mail("<1@x>", subject="Rechnung"))
    ollama = MagicMock()
    ollama.generate.side_effect = [
        OllamaResponse(text='{"tool": "search_mails", "args": {"query": "Rechnung"}}', model="m"),
        OllamaResponse(text='{"final_answer": "Gefunden: 1 Mail."}', model="m"),
    ]

    service = ChatService(storage, ollama, "mistral:latest", user_id)
    result = service.send_message([], "Suche Rechnungen")

    assert result.final_answer == "Gefunden: 1 Mail."
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].tool == "search_mails"


def test_send_message_unparsable_response_is_final_answer(storage, user_id):
    ollama = MagicMock()
    ollama.generate.return_value = OllamaResponse(text="Nur Fließtext, kein JSON.", model="m")

    service = ChatService(storage, ollama, "mistral:latest", user_id)
    result = service.send_message([], "Hi")

    assert result.final_answer == "Nur Fließtext, kein JSON."


def test_send_message_unknown_tool_reports_error_and_continues(storage, user_id):
    ollama = MagicMock()
    ollama.generate.side_effect = [
        OllamaResponse(text='{"tool": "delete_everything", "args": {}}', model="m"),
        OllamaResponse(text='{"final_answer": "Das kann ich nicht."}', model="m"),
    ]

    service = ChatService(storage, ollama, "mistral:latest", user_id)
    result = service.send_message([], "Lösch alles")

    assert result.final_answer == "Das kann ich nicht."
    assert "Unbekanntes Tool" in result.tool_calls[0].result_summary


def test_send_message_gives_up_after_max_steps(storage, user_id):
    ollama = MagicMock()
    ollama.generate.return_value = OllamaResponse(text='{"tool": "category_counts", "args": {}}', model="m")

    service = ChatService(storage, ollama, "mistral:latest", user_id)
    result = service.send_message([], "Endlosschleife")

    assert "nicht rechtzeitig" in result.final_answer
    assert len(result.tool_calls) == 5
