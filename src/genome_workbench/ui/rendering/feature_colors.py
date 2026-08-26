"""Shared feature-type color palette for linear and circular canvases."""

from __future__ import annotations

from PySide6.QtGui import QColor

_FEATURE_COLORS: dict[str, QColor] = {
    "CDS": QColor("#3b82c4"),
    "gene": QColor("#6b7280"),
    "tRNA": QColor("#e08a2c"),
    "rRNA": QColor("#8a4fd1"),
    "repeat_region": QColor("#3aa66b"),
    "promoter": QColor("#d1608a"),
    "misc_feature": QColor("#9aa0a6"),
    "source": QColor("#c9cdd3"),
}
_DEFAULT_COLOR = QColor("#9aa0a6")


def feature_color(feature_type: str) -> QColor:
    return _FEATURE_COLORS.get(feature_type, _DEFAULT_COLOR)
