"""Thin whole-genome overview strip with a draggable viewport rectangle.

Clicking or dragging anywhere on the strip jumps/pans the main canvas —
this is the primary way to navigate to a distant region without zooming out
first (mouse-only navigation, no coordinate typing required).
"""

from __future__ import annotations

from PySide6.QtCore import QRect, Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPaintEvent
from PySide6.QtWidgets import QWidget

from genome_workbench.domain.models import Feature
from genome_workbench.ui.rendering.feature_colors import feature_color


class Minimap(QWidget):
    viewportRequested = Signal(int, int)  # start0, end0

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(28)
        self._sequence_length = 0
        self._features: list[Feature] = []
        self._view_start0 = 0
        self._view_end0 = 0
        self._dragging = False
        self._color_overrides: dict[str, str] = {}

    def set_color_overrides(self, overrides: dict[str, str]) -> None:
        self._color_overrides = overrides
        self.update()

    def set_record_length(self, length: int) -> None:
        self._sequence_length = max(0, length)
        self.update()

    def set_features(self, features: list[Feature]) -> None:
        self._features = features
        self.update()

    def set_viewport(self, start0: int, end0: int) -> None:
        self._view_start0, self._view_end0 = start0, end0
        self.update()

    def _x_for_position(self, position0: int) -> float:
        if self._sequence_length <= 0:
            return 0.0
        return position0 / self._sequence_length * self.width()

    def _position_for_x(self, x: float) -> int:
        if self._sequence_length <= 0:
            return 0
        fraction = max(0.0, min(1.0, x / max(self.width(), 1)))
        return int(fraction * self._sequence_length)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#e5e7eb"))
        if self._sequence_length <= 0:
            painter.end()
            return

        painter.setPen(Qt.PenStyle.NoPen)
        for feature in self._features:
            x0 = self._x_for_position(feature.start0)
            x1 = self._x_for_position(feature.end0)
            width = max(1.0, x1 - x0)
            painter.setBrush(feature_color(feature.type, self._color_overrides))
            painter.drawRect(QRect(int(x0), 6, int(width), self.height() - 12))

        vx0 = self._x_for_position(self._view_start0)
        vx1 = self._x_for_position(self._view_end0)
        painter.setPen(QColor("#1f5fa8"))
        painter.setBrush(QColor(59, 130, 196, 60))
        painter.drawRect(QRect(int(vx0), 0, max(2, int(vx1 - vx0)), self.height() - 1))
        painter.end()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self._dragging = True
        self._jump_to(event.position().x())

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._dragging:
            self._jump_to(event.position().x())

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        self._dragging = False

    def _jump_to(self, x: float) -> None:
        center = self._position_for_x(x)
        half_width = max(1, (self._view_end0 - self._view_start0) // 2)
        start0 = max(0, center - half_width)
        end0 = min(self._sequence_length, center + half_width)
        self.viewportRequested.emit(start0, end0)
