"""Runs blocking work (IMAP, Ollama, ...) off the GUI thread so the window stays responsive
and callers can show a busy indicator instead of freezing with no feedback.
"""

from __future__ import annotations

import inspect
from typing import Callable

from PyQt6.QtCore import QObject, QRunnable, QThreadPool, pyqtSignal

from mailorganizer.utils.logger import get_logger

logger = get_logger("ui.workers")


class _WorkerSignals(QObject):
    finished = pyqtSignal(object)
    error = pyqtSignal(str)
    progress = pyqtSignal(int, int)  # (current, total)


class _FunctionWorker(QRunnable):
    """Wraps a callable to run on a QThreadPool thread; emits finished/error via Qt signals
    (which are automatically delivered back on the main thread)."""

    def __init__(self, fn: Callable, *args, **kwargs):
        super().__init__()
        # QThreadPool.start() takes C++ ownership of a QRunnable and auto-deletes it (and,
        # transitively, this object's `signals` QObject) as soon as run() returns — which can
        # race with this thread still using `self.signals` to emit `finished`/`error`, or with
        # the main thread's callback still running. Disabling auto-delete keeps the object
        # alive under Python's own refcounting (see `_active_workers` below) until we're
        # fully done with it.
        self.setAutoDelete(False)
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = _WorkerSignals()

    def run(self) -> None:
        kwargs = dict(self.kwargs)
        try:
            params = inspect.signature(self.fn).parameters
            if "progress_callback" in params:
                kwargs["progress_callback"] = self.signals.progress.emit
        except (TypeError, ValueError):
            pass  # builtins / C callables without an inspectable signature: skip progress support

        try:
            result = self.fn(*self.args, **kwargs)
        except Exception as exc:  # noqa: BLE001 - surface any failure to the caller instead of crashing the thread
            logger.error("Background task failed: %s", exc)
            self.signals.error.emit(str(exc))
            return
        self.signals.finished.emit(result)


# QRunnable is not a QObject, so PyQt6 has nothing to keep the Python-side worker (and its
# QObject-based signals) alive once run_in_background() returns and its local `worker`
# variable goes out of scope. Without this, CPython can garbage-collect the worker (and the
# C++ side deletes its `_WorkerSignals`) while the QThreadPool thread is still running it,
# crashing the process when it later tries to emit a signal on the deleted object. Keeping a
# strong reference here until the task finishes (success or error) prevents that.
_active_workers: set[_FunctionWorker] = set()


def run_in_background(
    fn: Callable,
    *args,
    on_success: Callable[[object], None] | None = None,
    on_error: Callable[[str], None] | None = None,
    on_progress: Callable[[int, int], None] | None = None,
    **kwargs,
) -> None:
    """Run `fn(*args, **kwargs)` on a background thread.

    `on_success` receives fn's return value; `on_error` receives the exception message.
    If `fn` accepts a `progress_callback` keyword argument, it is provided automatically and
    `on_progress(current, total)` is called for each emission.
    """
    worker = _FunctionWorker(fn, *args, **kwargs)
    _active_workers.add(worker)

    def _release(*_args: object) -> None:
        _active_workers.discard(worker)

    worker.signals.finished.connect(_release)
    worker.signals.error.connect(_release)
    if on_success is not None:
        worker.signals.finished.connect(on_success)
    if on_error is not None:
        worker.signals.error.connect(on_error)
    if on_progress is not None:
        worker.signals.progress.connect(on_progress)
    QThreadPool.globalInstance().start(worker)
