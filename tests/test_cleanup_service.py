from __future__ import annotations

import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from mailorganizer.models.mail import MailData
from mailorganizer.services.cleanup_service import CleanupService
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
        body="body",
    )
    defaults.update(overrides)
    return MailData(**defaults)


def test_archive_older_than(storage, user_id):
    old_mail = make_mail("<old@x>", received_at=datetime.now() - timedelta(days=100))
    new_mail = make_mail("<new@x>", received_at=datetime.now())
    storage.save_mail(user_id, old_mail)
    storage.save_mail(user_id, new_mail)

    summary = CleanupService(storage).run(user_id, archive_older_than_days=90)

    assert summary.archived == 1
    active = storage.list_mails(user_id)
    assert len(active) == 1
    assert active[0].message_id == "<new@x>"


def test_delete_spam(storage, user_id):
    spam_mail = make_mail("<spam@x>", is_spam=True)
    normal_mail = make_mail("<normal@x>")
    storage.save_mail(user_id, spam_mail)
    storage.save_mail(user_id, normal_mail)

    summary = CleanupService(storage).run(user_id, delete_spam=True)

    assert summary.spam_deleted == 1
    remaining = storage.list_mails_for_cleanup(user_id)
    assert len(remaining) == 1
    assert remaining[0].message_id == "<normal@x>"


def test_delete_duplicates_keeps_newest(storage, user_id):
    received = datetime(2024, 1, 1, 10, 0, 0)
    mail1 = make_mail("<dup1@x>", sender="dup@x.com", subject="Same", received_at=received)
    mail2 = make_mail("<dup2@x>", sender="dup@x.com", subject="Same", received_at=received)
    storage.save_mail(user_id, mail1)
    storage.save_mail(user_id, mail2)

    summary = CleanupService(storage).run(user_id, delete_duplicates=True)

    assert summary.duplicates_deleted == 1
    remaining = storage.list_mails_for_cleanup(user_id)
    assert len(remaining) == 1
    # the newest inserted row (highest id) is kept
    assert remaining[0].message_id == "<dup2@x>"


def test_run_with_no_options_does_nothing(storage, user_id):
    storage.save_mail(user_id, make_mail("<a@x>"))
    summary = CleanupService(storage).run(user_id)
    assert summary.total_affected == 0
    assert len(storage.list_mails(user_id)) == 1


def test_archive_mails_by_sender(storage, user_id):
    storage.save_mail(user_id, make_mail("<s1@x>", sender="newsletter@shop.com"))
    storage.save_mail(user_id, make_mail("<s2@x>", sender="newsletter@shop.com"))
    storage.save_mail(user_id, make_mail("<other@x>", sender="friend@x.com"))

    count = storage.archive_mails_by_sender(user_id, "newsletter@shop.com")

    assert count == 2
    active = storage.list_mails(user_id)
    assert len(active) == 1
    assert active[0].sender == "friend@x.com"
