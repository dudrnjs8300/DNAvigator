"""Atomic file writes: write to a temp file beside the destination, fsync, then replace.

Never leaves a partially-written file at the destination path, even on crash
or interrupted write. Callers doing export must validate the temp file (e.g.
reimport semantic comparison) *before* calling :func:`atomic_replace`.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Callable
from pathlib import Path


def write_atomic(destination: Path, write_fn: Callable[[Path], None]) -> None:
    """Call ``write_fn(temp_path)`` to populate a temp file, then atomically replace destination.

    ``write_fn`` must fully write and the temp file will be fsync'd and closed
    before the atomic replace. If ``write_fn`` raises, the temp file is
    removed and ``destination`` is left untouched.
    """
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)

    fd, temp_name = tempfile.mkstemp(
        dir=str(destination.parent),
        prefix=f".{destination.name}.",
        suffix=".tmp",
    )
    temp_path = Path(temp_name)
    os.close(fd)  # write_fn opens its own handle; we only reserved the name
    try:
        write_fn(temp_path)
        _fsync_path(temp_path)
        os.replace(temp_path, destination)
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise


def _fsync_path(path: Path) -> None:
    fd = os.open(str(path), os.O_RDWR)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
