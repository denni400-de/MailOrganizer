from __future__ import annotations

import pytest

pytest.importorskip("PyQt6")

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

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


def test_run_in_background_success(qapp):
    results = {}

    run_in_background(lambda x: x * 2, 21, on_success=lambda r: results.update(ok=r))

    _run_until(qapp, lambda: "ok" in results)

    assert results["ok"] == 42


def test_run_in_background_error(qapp):
    def failing():
        raise ValueError("boom")

    results = {}
    run_in_background(failing, on_error=lambda e: results.update(err=e))

    _run_until(qapp, lambda: "err" in results)

    assert results["err"] == "boom"


def test_run_in_background_progress_callback(qapp):
    def with_progress(n, progress_callback=None):
        for i in range(n):
            if progress_callback:
                progress_callback(i, n)
        return "done"

    results = {}
    progress_events = []
    run_in_background(
        with_progress,
        5,
        on_success=lambda r: results.update(ok=r),
        on_progress=lambda c, t: progress_events.append((c, t)),
    )

    _run_until(qapp, lambda: "ok" in results)

    assert results["ok"] == "done"
    assert progress_events == [(0, 5), (1, 5), (2, 5), (3, 5), (4, 5)]


def test_run_in_background_without_progress_handler_does_not_crash(qapp):
    """A worker whose fn takes progress_callback but the caller doesn't pass on_progress:
    the callback must still be safely callable (regression test for a QRunnable lifecycle
    bug where its signals object could be destroyed mid-run)."""

    def with_progress(n, progress_callback=None):
        for i in range(n):
            if progress_callback:
                progress_callback(i, n)
        return "done"

    results = {}
    run_in_background(with_progress, 10, on_success=lambda r: results.update(ok=r))

    _run_until(qapp, lambda: "ok" in results)

    assert results["ok"] == "done"


def test_run_in_background_many_concurrent_tasks(qapp):
    """Several overlapping background tasks shouldn't interfere with each other's lifecycle."""
    results = []

    for i in range(10):
        run_in_background(lambda x: x, i, on_success=results.append)

    _run_until(qapp, lambda: len(results) == 10)

    assert sorted(results) == list(range(10))
