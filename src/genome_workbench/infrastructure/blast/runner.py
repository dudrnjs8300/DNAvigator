"""Synchronous BLAST+ subprocess execution.

Blocking by design — callers (application/blast_service.py + a UI-layer
worker thread) are responsible for keeping this off the Qt UI thread. Always
argument lists, never shell strings.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from genome_workbench.infrastructure.blast.detector import subprocess_kwargs


class BlastExecutionError(RuntimeError):
    def __init__(self, command: list[str], exit_code: int, stderr: str) -> None:
        self.command = command
        self.exit_code = exit_code
        self.stderr = stderr
        super().__init__(
            f"command failed (exit {exit_code}): {' '.join(command)}\n{stderr.strip()}"
        )


@dataclass(slots=True)
class CommandResult:
    command: list[str]
    exit_code: int
    stdout: str
    stderr: str


def run_command(command: list[str], timeout_seconds: float = 600.0) -> CommandResult:
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        **subprocess_kwargs(),
    )
    return CommandResult(
        command=command, exit_code=result.returncode, stdout=result.stdout, stderr=result.stderr
    )


def run_command_or_raise(command: list[str], timeout_seconds: float = 600.0) -> CommandResult:
    result = run_command(command, timeout_seconds)
    if result.exit_code != 0:
        raise BlastExecutionError(command, result.exit_code, result.stderr)
    return result


def run_search_to_file(
    command: list[str], raw_output_path: Path, timeout_seconds: float = 600.0
) -> CommandResult:
    """Run a BLAST search command and write raw tabular stdout to a file (job artifact)."""
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        **subprocess_kwargs(),
    )
    raw_output_path.parent.mkdir(parents=True, exist_ok=True)
    raw_output_path.write_text(result.stdout, encoding="utf-8")
    if result.returncode != 0:
        raise BlastExecutionError(command, result.returncode, result.stderr)
    return CommandResult(
        command=command, exit_code=result.returncode, stdout=result.stdout, stderr=result.stderr
    )
