"""Application entry point."""

from __future__ import annotations

import sys

from PyQt6.QtWidgets import QApplication

from mailorganizer.config.settings import get_settings
from mailorganizer.ui.main_window import MainWindow
from mailorganizer.utils.logger import setup_logging


def main() -> int:
    settings = get_settings()
    setup_logging(settings.log_level, settings.resolved_log_dir)

    app = QApplication(sys.argv)
    app.setApplicationName("Mail Organizer")

    window = MainWindow(settings)
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
