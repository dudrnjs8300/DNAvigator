from __future__ import annotations

from collections.abc import Callable

from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QWidget


def make_action(
    parent: QWidget,
    text: str,
    triggered: Callable[[], None] | None = None,
    shortcut: QKeySequence.StandardKey | str | None = None,
    enabled: bool = True,
    tooltip: str | None = None,
) -> QAction:
    action = QAction(text, parent)
    if triggered is not None:
        action.triggered.connect(triggered)
    if shortcut is not None:
        action.setShortcut(shortcut)
    action.setEnabled(enabled)
    if tooltip:
        action.setToolTip(tooltip)
        action.setStatusTip(tooltip)
    return action
