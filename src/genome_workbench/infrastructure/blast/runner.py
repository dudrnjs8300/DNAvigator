"""Synchronous BLAST+ subprocess execution.

Blocking by design — callers (application/blast_service.py + a UI-layer
worker thread) are responsible for keeping this off the Qt UI thread. Always
argument lists, never shell strings.
"""

from __future__ import annotations

import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from genome_workbench.infrastructure.blast.detector import subprocess_kwargs

_POLL_INTERVAL_SECONDS = 0.2


class BlastExecutionError(RuntimeError):
    def __init__(self, command: list[str], exit_code: int, stderr: str) -> None:
        self.command = command
        self.exit_code = exit_code
        self.stderr = stderr
        super().__init__(
            f"command failed (exit {exit_code}): {' '.join(command)}\n{stderr.strip()}"
        )


class BlastCancelledError(RuntimeError):
    def __init__(self, command: list[str]) -> None:
        self.command = command
        super().__init__("BLAST job was cancelled by the user.")


@dataclass(slots=True)
class CommandResult:
    command: list[str]
    exit_code: int
    stdout: str
    stderr: str


def _run_popen(
    command: list[str],
    timeout_seconds: float,
    cancel_event: threading.Event | None,
) -> CommandResult:
    """Run ``command`` via Popen, polling so an external thread can request
    cancellation (setting ``cancel_event``) without waiting for the whole
    subprocess to finish. ``subprocess.run`` can't be interrupted this way --
    once called, it blocks until the process exits or the timeout fires.
    """
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        **subprocess_kwargs(),
    )
    started_at = time.monotonic()
    while True:
        try:
            stdout, stderr = process.communicate(timeout=_POLL_INTERVAL_SECONDS)
            break
        except subprocess.TimeoutExpired:
            if cancel_event is not None and cancel_event.is_set():
                process.kill()
                process.communicate()
                raise BlastCancelledError(command) from None
            if time.monotonic() - started_at > timeout_seconds:
                process.kill()
                process.communicate()
                raise subprocess.TimeoutExpired(command, timeout_seconds) from None
    return CommandResult(
        command=command, exit_code=process.returncode, stdout=stdout, stderr=stderr
    )


def run_command(
    command: list[str],
    timeout_seconds: float = 600.0,
    cancel_event: threading.Event | None = None,
) -> CommandResult:
    return _run_popen(command, timeout_seconds, cancel_event)


def run_command_or_raise(
    command: list[str],
    timeout_seconds: float = 600.0,
    cancel_event: threading.Event | None = None,
) -> CommandResult:
    result = run_command(command, timeout_seconds, cancel_event)
    if result.exit_code != 0:
        raise BlastExecutionError(command, result.exit_code, result.stderr)
    return result


def run_search_to_file(
    command: list[str],
    raw_output_path: Path,
    timeout_seconds: float = 600.0,
    cancel_event: threading.Event | None = None,
) -> CommandResult:
    """Run a BLAST search command and write raw tabular stdout to a file (job artifact)."""
    result = _run_popen(command, timeout_seconds, cancel_event)
    raw_output_path.parent.mkdir(parents=True, exist_ok=True)
    raw_output_path.write_text(result.stdout, encoding="utf-8")
    if result.exit_code != 0:
        raise BlastExecutionError(command, result.exit_code, result.stderr)
    return result
