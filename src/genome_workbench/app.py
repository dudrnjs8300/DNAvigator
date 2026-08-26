"""GUI application bootstrap."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from genome_workbench.infrastructure.logging_setup import configure_logging
from genome_workbench.ui.main_window import MainWindow
from genome_workbench.version import APP_NAME, APP_VERSION


def run_app(argv: list[str] | None = None) -> int:
    configure_logging()
    app = QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    window = MainWindow()
    window.show()
    return app.exec()
