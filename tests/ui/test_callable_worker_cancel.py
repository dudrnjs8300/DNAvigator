"""Verifies CallableWorker.with_cancel_support()/cancel() wiring: a function
that respects the injected cancel_event should have its thread interrupted,
and the worker should surface that as a `failed` signal the UI can recognize
as "cancelled" rather than a real error (see MainWindow._on_blast_job_failed).
"""

from __future__ import annotations

import threading

from genome_workbench.ui.workers.callable_worker import CallableWorker


def _slow_task_that_checks_cancellation(timeout: float, cancel_event: threading.Event) -> str:
    was_cancelled = cancel_event.wait(timeout=timeout)
    if was_cancelled:
        raise RuntimeError("BLAST job was cancelled by the user.")
    return "completed without cancellation"


def test_cancel_interrupts_a_running_worker_and_reports_cancellation(qtbot):
    # long timeout: only cancel() (not the timeout itself) should unblock this.
    # Signals cross threads via a queued connection, so waiting must pump the
    # Qt event loop (qtbot.waitSignal) rather than just join the thread
    # (worker.wait()), or the queued delivery never happens.
    worker = CallableWorker(_slow_task_that_checks_cancellation, 5.0).with_cancel_support()
    worker.start()
    qtbot.wait(200)
    assert not worker.cancel_event.is_set()

    with qtbot.waitSignal(worker.failed, timeout=3000, raising=True) as blocker:
        worker.cancel()

    assert "cancelled by the user" in blocker.args[0]


def test_without_cancel_the_worker_completes_normally(qtbot):
    # short timeout, never cancelled: the task should just finish on its own
    worker = CallableWorker(_slow_task_that_checks_cancellation, 0.2).with_cancel_support()

    with qtbot.waitSignal(worker.succeeded, timeout=3000, raising=True) as blocker:
        worker.start()

    assert blocker.args[0] == "completed without cancellation"
