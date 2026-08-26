"""Verifies that a running BLAST+ subprocess can actually be cancelled from
another thread (AT-08 gap: previously there was no way to interrupt a job
once started). Uses a plain Python sleep script instead of a real/mock BLAST
executable so this stays fast and independent of any BLAST+ installation.
"""

from __future__ import annotations

import sys
import threading
import time

import pytest

from genome_workbench.infrastructure.blast.runner import (
    BlastCancelledError,
    run_command,
)

_SLEEP_30S = [sys.executable, "-c", "import time; time.sleep(30)"]


def test_run_command_without_cancel_event_runs_to_completion():
    result = run_command([sys.executable, "-c", "print('hi')"], timeout_seconds=10)
    assert result.exit_code == 0
    assert "hi" in result.stdout


def test_cancelling_mid_run_kills_the_process_quickly():
    cancel_event = threading.Event()

    def cancel_shortly_after_start() -> None:
        time.sleep(0.5)
        cancel_event.set()

    threading.Thread(target=cancel_shortly_after_start, daemon=True).start()

    started_at = time.monotonic()
    with pytest.raises(BlastCancelledError):
        run_command(_SLEEP_30S, timeout_seconds=60, cancel_event=cancel_event)
    elapsed = time.monotonic() - started_at

    # the underlying process sleeps for 30s; a working cancel must interrupt
    # it almost immediately rather than waiting the full duration
    assert elapsed < 5.0


def test_cancel_event_set_before_start_cancels_immediately():
    cancel_event = threading.Event()
    cancel_event.set()

    started_at = time.monotonic()
    with pytest.raises(BlastCancelledError):
        run_command(_SLEEP_30S, timeout_seconds=60, cancel_event=cancel_event)
    elapsed = time.monotonic() - started_at

    assert elapsed < 2.0
