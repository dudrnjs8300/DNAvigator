"""Project file locking: detect a second instance opening the same project,
and (by the lock file's mere presence on next open) an unclean previous exit.

A clean :func:`release_lock` on normal close removes the file; if it is still
there when the project is opened again, that in itself is the "abnormal exit"
signal spec 12.4 asks for — no separate periodic snapshot mechanism is
needed because every mutation already commits immediately to the project's
SQLite file (see application/commands.py), so there is no unsaved-edit
buffer that could be lost.
"""

from __future__ import annotations

import json
import os
import socket
from dataclasses import asdict, dataclass
from pathlib import Path

from genome_workbench.domain.models import utc_now


@dataclass(frozen=True, slots=True)
class LockInfo:
    pid: int
    hostname: str
    opened_at: str


class ProjectLockedError(RuntimeError):
    def __init__(self, lock_info: LockInfo) -> None:
        self.lock_info = lock_info
        super().__init__(
            f"project is already open (pid={lock_info.pid}, host={lock_info.hostname}, "
            f"since {lock_info.opened_at}) or was not closed cleanly last time"
        )


def _lock_path(project_path: Path) -> Path:
    return project_path.with_name(project_path.name + ".lock")


def read_lock(project_path: Path) -> LockInfo | None:
    lock_path = _lock_path(project_path)
    if not lock_path.exists():
        return None
    try:
        data = json.loads(lock_path.read_text(encoding="utf-8"))
        return LockInfo(pid=data["pid"], hostname=data["hostname"], opened_at=data["opened_at"])
    except (OSError, json.JSONDecodeError, KeyError, TypeError):
        return None


def acquire_lock(project_path: Path) -> None:
    lock_path = _lock_path(project_path)
    info = LockInfo(pid=os.getpid(), hostname=socket.gethostname(), opened_at=utc_now())
    lock_path.write_text(json.dumps(asdict(info)), encoding="utf-8")


def release_lock(project_path: Path) -> None:
    _lock_path(project_path).unlink(missing_ok=True)
