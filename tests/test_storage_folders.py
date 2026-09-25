from __future__ import annotations

import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from mailorganizer.models.mail import MailData
from mailorganizer.services.storage_service import StorageService


@pytest.fixture
def storage():
    with tempfile.TemporaryDirectory() as tmp:
        yield StorageService(Path(tmp) / "test.db")


@pytest.fixture
def user_id(storage):
    user = storage.get_or_create_user("a@b.com", "imap.x.com", "smtp.x.com", "encpass")
    return user.id


def make_mail(message_id, folder="INBOX", **overrides) -> MailData:
    defaults = dict(
        message_id=message_id,
        sender="s@x.com",
        recipients=["a@b.com"],
        subject="Subject",
        received_at=datetime.now(),
        body="body",
        folder=folder,
    )
    defaults.update(overrides)
    return MailData(**defaults)


def test_save_mail_persists_folder(storage, user_id):
    storage.save_mail(user_id, make_mail("<a@x>", folder="Archive"))
    mails = storage.list_mails(user_id, include_archived=True)
    assert mails[0].folder == "Archive"


def test_list_mails_filters_by_folder(storage, user_id):
    storage.save_mail(user_id, make_mail("<inbox@x>", folder="INBOX"))
    storage.save_mail(user_id, make_mail("<archive@x>", folder="Archive"))

    inbox_only = storage.list_mails(user_id, folder="INBOX")
    assert [m.message_id for m in inbox_only] == ["<inbox@x>"]

    all_folders = storage.list_mails(user_id)
    assert len(all_folders) == 2


def test_list_known_folders(storage, user_id):
    storage.save_mail(user_id, make_mail("<a@x>", folder="INBOX"))
    storage.save_mail(user_id, make_mail("<b@x>", folder="Archive"))
    storage.save_mail(user_id, make_mail("<c@x>", folder="Archive"))

    folders = storage.list_known_folders(user_id)
    assert folders == ["Archive", "INBOX"]


def test_migration_adds_folder_column_to_legacy_db():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = str(Path(tmp) / "legacy.db")
        conn = sqlite3.connect(db_path)
        conn.execute(
            """CREATE TABLE users (
                id INTEGER PRIMARY KEY, imap_server TEXT NOT NULL, imap_port INTEGER DEFAULT 993,
                smtp_server TEXT NOT NULL, smtp_port INTEGER DEFAULT 587,
                email_address TEXT UNIQUE NOT NULL, password_encrypted TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"""
        )
        conn.execute(
            """CREATE TABLE mails (
                id INTEGER PRIMARY KEY, message_id TEXT UNIQUE NOT NULL, user_id INTEGER NOT NULL,
                sender TEXT NOT NULL, recipients TEXT NOT NULL, cc TEXT, subject TEXT NOT NULL,
                body TEXT, html_body TEXT, received_at TIMESTAMP NOT NULL,
                is_read BOOLEAN DEFAULT 0, is_archived BOOLEAN DEFAULT 0,
                is_important BOOLEAN DEFAULT 0, is_spam BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"""
        )
        conn.execute(
            "INSERT INTO users (id, imap_server, smtp_server, email_address, password_encrypted) "
            "VALUES (1, 'x', 'y', 'a@b.com', 'pw')"
        )
        conn.execute(
            "INSERT INTO mails (message_id, user_id, sender, recipients, subject, received_at) "
            "VALUES ('<1@x>', 1, 's@x.com', '[]', 'Test', '2024-01-01 10:00:00')"
        )
        conn.commit()
        conn.close()

        columns_before = {row[1] for row in sqlite3.connect(db_path).execute("PRAGMA table_info(mails)")}
        assert "folder" not in columns_before

        storage = StorageService(db_path)

        columns_after = {row[1] for row in sqlite3.connect(db_path).execute("PRAGMA table_info(mails)")}
        assert "folder" in columns_after

        mails = storage.list_mails(1, include_archived=True, include_spam=True)
        assert mails[0].folder == "INBOX"
