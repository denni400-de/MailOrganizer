from __future__ import annotations

import tempfile
import threading
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
        # closeEvent is now asynchronous (hides + polls the thread pool instead of blocking),
        # so give it a chance to actually settle before the next test reuses this QApplication —
        # otherwise a leftover _shutdown_timer keeps firing across tests.
        win.close()
        _run_until(qapp, lambda: getattr(win, "_shutdown_ready", False), timeout_ms=2000)


def test_sync_mails_ignores_reentrant_calls_while_in_flight(main_window, qapp):
    """Regression test: the sync_timer (or a settings save) firing sync_mails() again while
    a previous sync is still running on its background thread must not start a second
    *concurrent* _sync_task — disabling the toolbar button alone doesn't stop the QTimer.
    A request made while busy is deferred and re-run exactly once afterwards (it must not be
    silently dropped, e.g. an explicit post-settings-save sync), not fired once per call."""
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
        main_window.sync_mails()  # collapses into one deferred re-run ...
        main_window.sync_mails()  # ... this one too, not a second re-run

        _run_until(qapp, lambda: not main_window._sync_in_progress and call_count["n"] >= 2)
        # give any (incorrect) extra re-run a moment to happen before asserting it didn't
        _run_until(qapp, lambda: False, timeout_ms=400)

        assert call_count["n"] == 2


def test_close_event_does_not_block_gui_thread(main_window, qapp):
    """Regression test: closeEvent must not freeze the GUI thread while draining the thread
    pool (a single blocking waitForDone() would just trade the teardown-crash risk for an
    unresponsive-app complaint) — close() should return quickly, with the drain happening via
    a polled QTimer while the event loop keeps running."""
    done = {"finished": False}

    def slow_task():
        time.sleep(0.5)
        done["finished"] = True
        return 1

    run_in_background(slow_task)

    start = time.monotonic()
    main_window.close()
    close_call_elapsed = time.monotonic() - start

    assert close_call_elapsed < 0.2, "close() must return immediately, not block on the task"
    assert done["finished"] is False, "the task shouldn't be done yet right after close() returns"

    _run_until(qapp, lambda: done["finished"], timeout_ms=3000)

    assert done["finished"] is True


def test_close_event_cancels_in_flight_analysis(main_window):
    """Regression test: closing the window must cooperatively cancel an in-flight analyze
    loop (via its existing cancel Event) instead of only waiting out however many Ollama
    calls are left, which can easily exceed any reasonable bounded shutdown wait."""
    main_window._analyze_cancel_event = threading.Event()
    assert not main_window._analyze_cancel_event.is_set()

    main_window.close()

    assert main_window._analyze_cancel_event.is_set()
