"""Global fallback for exceptions that escape a Qt slot (a menu action, a
dialog's OK/Apply handler, a worker's success callback, ...).

Without this, PySide6 just forwards the exception to the default
``sys.excepthook`` (prints the traceback) and the event loop keeps running --
invisible in a windowed build with no console, so the user either sees
nothing happen or, if a console happens to be attached, a raw Python
traceback with no guidance. This installs a hook that always logs the full
traceback to the existing log file and shows the user something actionable,
with a specific message for "database is locked" (sqlite3.OperationalError),
which a project file on a network drive or a OneDrive/Dropbox-synced folder
can trigger even in ordinary single-user use.
"""

from __future__ import annotations

import logging
import sqlite3
import sys
import traceback
from types import TracebackType

from PySide6.QtWidgets import QApplication, QMessageBox

logger = logging.getLogger("genome_workbench")

_LOCKED_MESSAGE = (
    "This project file appears to be locked by another program, so the last "
    "action could not complete.\n\n"
    "This usually happens when the project file is in a folder synced by "
    "OneDrive/Dropbox/Google Drive, on a network drive, or open in another "
    "running copy of DNAvigator at the same time. Close any other copy of "
    "DNAvigator that has this project open, pause cloud sync for this folder, "
    "and try again. Keeping the project file on a local drive avoids this."
)


def _is_database_locked(exc: BaseException) -> bool:
    return isinstance(exc, sqlite3.OperationalError) and "locked" in str(exc).lower()


def install() -> None:
    def _handle(
        exc_type: type[BaseException], exc: BaseException, tb: TracebackType | None
    ) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc, tb)
            return
        logger.error(
            "Unhandled exception:\n%s",
            "".join(traceback.format_exception(exc_type, exc, tb)),
        )
        if _is_database_locked(exc):
            title, message = "Project File Locked", _LOCKED_MESSAGE
        else:
            title = "Unexpected Error"
            message = (
                f"An unexpected error occurred and the last action did not complete:\n\n"
                f"{exc_type.__name__}: {exc}\n\n"
                r"Details were written to %LOCALAPPDATA%\DNAvigator\logs\genome_workbench.log."
            )
        if QApplication.instance() is not None:
            QMessageBox.critical(None, title, message)

    sys.excepthook = _handle
