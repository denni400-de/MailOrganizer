"""Background scheduling of periodic mail sync + analysis, decoupled from Qt."""

from __future__ import annotations

import threading
from typing import Callable

from mailorganizer.utils.logger import get_logger

logger = get_logger("scheduler_service")


class SchedulerService:
    """Runs a callback on a fixed interval in a background thread until stopped.

    Kept independent of PyQt's QTimer so it can also run in headless/CLI contexts;
    the UI layer may instead wire a QTimer directly to the same callback.
    """

    def __init__(self, interval_seconds: int, callback: Callable[[], None]):
        self.interval_seconds = interval_seconds
        self.callback = callback
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="mailorganizer-scheduler")
        self._thread.start()
        logger.info("Scheduler started with interval=%ss", self.interval_seconds)

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
        logger.info("Scheduler stopped")

    def _run(self) -> None:
        while not self._stop_event.wait(self.interval_seconds):
            try:
                self.callback()
            except Exception:
                logger.exception("Scheduled task raised an exception")

    def run_now(self) -> None:
        """Run the callback immediately, outside of the interval schedule."""
        try:
            self.callback()
        except Exception:
            logger.exception("Manual scheduled task run raised an exception")
