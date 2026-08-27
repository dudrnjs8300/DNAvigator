"""Shared feature-type color palette for linear and circular canvases.

Defaults are a fixed built-in palette. Users can override any type's color
(or add colors for types outside the default set) via View > Feature
Colors...; overrides are a plain ``feature_type -> "#rrggbb"`` dict threaded
explicitly into each canvas via ``set_color_overrides()`` rather than kept
as hidden global state, so canvases stay easy to construct and test in
isolation. Persisted per-user (not per-project, same reasoning as the BLAST
database catalog and annotation templates -- D-007: a display preference
should follow the user across projects, not live inside one project file).
"""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtGui import QColor

from genome_workbench.infrastructure.filesystem.paths import app_data_dir

DEFAULT_FEATURE_COLORS: dict[str, str] = {
    "CDS": "#3b82c4",
    "gene": "#6b7280",
    "tRNA": "#e08a2c",
    "rRNA": "#8a4fd1",
    "repeat_region": "#3aa66b",
    "promoter": "#d1608a",
    "misc_feature": "#9aa0a6",
    "source": "#c9cdd3",
}
DEFAULT_COLOR = "#9aa0a6"


def feature_color(feature_type: str, overrides: dict[str, str] | None = None) -> QColor:
    if overrides and feature_type in overrides:
        return QColor(overrides[feature_type])
    return QColor(DEFAULT_FEATURE_COLORS.get(feature_type, DEFAULT_COLOR))


def _overrides_path(directory: Path | None = None) -> Path:
    return (directory if directory is not None else app_data_dir()) / "feature_colors.json"


def load_color_overrides(directory: Path | None = None) -> dict[str, str]:
    path = _overrides_path(directory)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {k: v for k, v in data.items() if isinstance(k, str) and isinstance(v, str)}


def save_color_overrides(overrides: dict[str, str], directory: Path | None = None) -> None:
    path = _overrides_path(directory)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(overrides, indent=2, sort_keys=True), encoding="utf-8")
