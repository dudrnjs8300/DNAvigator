"""GUI application bootstrap."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from genome_workbench.infrastructure.logging_setup import configure_logging
from genome_workbench.ui.main_window import MainWindow
from genome_workbench.version import APP_NAME, APP_VERSION


def run_app(argv: list[str] | None = None, open_project_path: str | None = None) -> int:
    configure_logging()
    app = QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    window = MainWindow()
    window.show()
    if open_project_path is not None:
        window.open_project_at_path(open_project_path)
    return app.exec()
