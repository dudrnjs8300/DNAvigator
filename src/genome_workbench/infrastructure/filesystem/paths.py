"""Windows user-data directory layout.

``%LOCALAPPDATA%/GenomeWorkbench`` holds settings, logs, and app-managed
tools. It is distinct from project files, which live wherever the user
chooses to save them.
"""

from __future__ import annotations

import os
from pathlib import Path

from genome_workbench.version import APP_NAME


def app_data_dir() -> Path:
    """Return ``%LOCALAPPDATA%/GenomeWorkbench`` (or an XDG/home fallback off-Windows)."""
    local_app_data = os.environ.get("LOCALAPPDATA")
    base = Path(local_app_data) if local_app_data else Path.home() / ".local" / "share"
    directory = base / APP_NAME
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def logs_dir() -> Path:
    directory = app_data_dir() / "logs"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def tools_dir() -> Path:
    directory = app_data_dir() / "tools"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def settings_file() -> Path:
    return app_data_dir() / "settings.json"


def recovery_dir() -> Path:
    directory = app_data_dir() / "recovery"
    directory.mkdir(parents=True, exist_ok=True)
    return directory
