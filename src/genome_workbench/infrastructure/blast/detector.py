"""Locate and version-check NCBI BLAST+ executables.

Never uses shell=True; always builds argument lists. On Windows, subprocess
creation flags suppress the console window that would otherwise flash for
each ``-version`` probe.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from genome_workbench.domain.blast_models import BlastInstallation

REQUIRED_EXECUTABLES = ("makeblastdb", "blastdbcmd", "blastn", "blastp", "blastx", "tblastn")

_COMMON_WINDOWS_INSTALL_DIRS = [
    Path(r"C:\Program Files\NCBI\blast-2.16.0+\bin"),
    Path(r"C:\Program Files\NCBI\blast\bin"),
]


def subprocess_kwargs() -> dict:
    kwargs: dict = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    return kwargs


def _executable_name(name: str) -> str:
    return f"{name}.exe" if sys.platform == "win32" else name


def find_executable(name: str, search_dir: Path | None = None) -> Path | None:
    exe_name = _executable_name(name)
    candidate_dirs: list[Path] = []
    if search_dir is not None:
        candidate_dirs.append(Path(search_dir))
    candidate_dirs.extend(_COMMON_WINDOWS_INSTALL_DIRS if sys.platform == "win32" else [])

    for directory in candidate_dirs:
        candidate = directory / exe_name
        if candidate.is_file():
            return candidate

    found_on_path = shutil.which(exe_name) or shutil.which(name)
    return Path(found_on_path) if found_on_path else None


def get_version(executable_path: Path, timeout_seconds: float = 10.0) -> str:
    try:
        result = subprocess.run(
            [str(executable_path), "-version"],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            **subprocess_kwargs(),
        )
        output = (result.stdout or result.stderr or "").strip()
        return output.splitlines()[0] if output else "unknown version"
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"version check failed: {exc}"


def detect_installation(search_dir: Path | None = None) -> BlastInstallation:
    installation = BlastInstallation(directory=str(search_dir) if search_dir else None)
    for name in REQUIRED_EXECUTABLES:
        path = find_executable(name, search_dir)
        if path is not None:
            installation.executables[name] = str(path)
            installation.versions[name] = get_version(path)
    return installation
