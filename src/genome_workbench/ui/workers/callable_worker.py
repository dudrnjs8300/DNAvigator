"""Runs a blocking callable (BLAST subprocess calls, database builds, ...) off
the Qt UI thread. Application/infrastructure code stays Qt-free; only this
thin adapter lives in the UI layer.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QThread, Signal


class CallableWorker(QThread):
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs
        self.cancel_event = threading.Event()

    def with_cancel_support(self) -> CallableWorker:
        """Opt in to cancellation: ``fn`` must accept a ``cancel_event`` kwarg
        (currently only BlastService.create_database/run_search do) and check
        it while the underlying subprocess runs.
        """
        self._kwargs["cancel_event"] = self.cancel_event
        return self

    def cancel(self) -> None:
        self.cancel_event.set()

    def run(self) -> None:
        try:
            result = self._fn(*self._args, **self._kwargs)
        except Exception as exc:  # noqa: BLE001 - reported to the UI, not swallowed
            self.failed.emit(str(exc))
            return
        self.succeeded.emit(result)
