from __future__ import annotations

import tempfile
import time
from pathlib import Path
from unittest.mock import patch

import pytest

pytest.importorskip("PyQt6")

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from mailorganizer.config.settings import Settings
from mailorganizer.services.mail_service import MailAccountCredentials
from mailorganizer.ui.main_window import MainWindow
from mailorganizer.ui.workers import run_in_background


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
def main_window(qapp):
    with tempfile.TemporaryDirectory() as tmp:
        settings = Settings(database_path=str(Path(tmp) / "test.db"))
        with patch("mailorganizer.ui.widgets.onboarding.QMessageBox"):
            win = MainWindow(settings)
            win.show()
        yield win
        win.close()


def test_sync_mails_ignores_reentrant_calls_while_in_flight(main_window, qapp):
    """Regression test: the sync_timer (or a settings save) firing sync_mails() again while
    a previous sync is still running on its background thread must not start a second
    concurrent _sync_task — disabling the toolbar button alone doesn't stop the QTimer."""
    user = main_window.storage.get_or_create_user("a@b.com", "imap.x.com", "smtp.x.com", "pw")
    main_window.user_id = user.id
    main_window.mail_credentials = MailAccountCredentials(
        email_address="a@b.com", password="pw", imap_server="imap.x.com", smtp_server="smtp.x.com"
    )

    call_count = {"n": 0}

    def slow_sync_task(*_args, **_kwargs):
        call_count["n"] += 1
        time.sleep(0.3)
        return 0

    with patch("mailorganizer.ui.main_window._sync_task", side_effect=slow_sync_task):
        main_window.sync_mails()
        main_window.sync_mails()
        main_window.sync_mails()

        _run_until(qapp, lambda: not main_window._sync_in_progress)

        assert call_count["n"] == 1


def test_close_event_drains_background_thread_pool(main_window):
    """Regression test: closing the window ends app.exec() and starts interpreter teardown;
    closeEvent must wait for in-flight background work first instead of letting it race
    against process shutdown."""
    done = {"finished": False}

    def slow_task():
        time.sleep(0.5)
        done["finished"] = True
        return 1

    run_in_background(slow_task)

    start = time.monotonic()
    main_window.close()
    elapsed = time.monotonic() - start

    assert done["finished"] is True
    assert elapsed >= 0.4
