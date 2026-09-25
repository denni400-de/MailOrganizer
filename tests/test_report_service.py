from __future__ import annotations

import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from mailorganizer.models.analysis import AnalysisResult
from mailorganizer.models.mail import MailData
from mailorganizer.services.report_service import ReportService
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


def test_report_counts_recent_mails_only(storage, user_id):
    recent = storage.save_mail(user_id, make_mail("<recent@x>", received_at=datetime.now()))
    storage.save_mail(user_id, make_mail("<old@x>", received_at=datetime.now() - timedelta(days=30)))

    report = ReportService(storage).generate_weekly_report(user_id)

    assert report.total_mails == 1


def test_report_top_senders(storage, user_id):
    for i in range(3):
        storage.save_mail(user_id, make_mail(f"<a{i}@x>", sender="frequent@x.com"))
    storage.save_mail(user_id, make_mail("<b@x>", sender="rare@x.com"))

    report = ReportService(storage).generate_weekly_report(user_id)

    assert report.top_senders[0] == ("frequent@x.com", 3)


def test_report_category_and_importance_stats(storage, user_id):
    mail = storage.save_mail(user_id, make_mail("<a@x>"))
    storage.save_analysis(
        mail.id,
        AnalysisResult(
            category="work",
            importance_score=5,
            sentiment="positive",
            summary="s",
            recommended_action="flag",
            ollama_model="mistral",
        ),
    )

    report = ReportService(storage).generate_weekly_report(user_id)

    assert report.category_counts == {"work": 1}
    assert report.importance_distribution == {5: 1}


def test_report_suggests_archiving_old_mails(storage, user_id):
    storage.save_mail(user_id, make_mail("<old@x>", received_at=datetime.now() - timedelta(days=100)))

    report = ReportService(storage).generate_weekly_report(user_id)

    assert any("archiviert" in s for s in report.suggested_actions)


def test_report_suggests_deleting_spam(storage, user_id):
    storage.save_mail(user_id, make_mail("<spam@x>", is_spam=True))

    report = ReportService(storage).generate_weekly_report(user_id)

    assert any("Spam" in s for s in report.suggested_actions)


def test_report_no_suggestions_when_clean(storage, user_id):
    storage.save_mail(user_id, make_mail("<a@x>"))
    mail = storage.list_mails(user_id)[0]
    storage.save_analysis(
        mail.id,
        AnalysisResult(
            category="work",
            importance_score=3,
            sentiment="neutral",
            summary="s",
            recommended_action="archive",
            ollama_model="mistral",
        ),
    )

    report = ReportService(storage).generate_weekly_report(user_id)

    assert report.suggested_actions == ["Keine Aufräum-Vorschläge — alles sieht aufgeräumt aus."]
