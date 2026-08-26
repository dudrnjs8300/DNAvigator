"""Circular genome map: ring backbone with strand-separated feature arcs.

Feature click selection is synchronized with the linear canvas / feature
table / inspector via MainWindow. Origin is drawn at 12 o'clock, genome
coordinate increasing clockwise.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QToolTip, QWidget

from genome_workbench.domain.coordinates import display_from_internal
from genome_workbench.domain.models import Feature, SequenceRecord
from genome_workbench.ui.rendering.feature_colors import feature_color

_MARGIN = 24
_RING_WIDTH = 14
_RING_GAP = 4


class CircularGenomeCanvas(QWidget):
    featureClicked = Signal(str)
    featureDoubleClicked = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setMinimumSize(240, 240)
        self._record: SequenceRecord | None = None
        self._features: list[Feature] = []
        self._selected_feature_id: str | None = None
        self._hover_feature_id: str | None = None

    def set_record(self, record: SequenceRecord | None, features: list[Feature]) -> None:
        self._record = record
        self._features = features
        self._selected_feature_id = None
        self.update()

    def set_features(self, features: list[Feature]) -> None:
        self._features = features
        self.update()

    def select_feature(self, feature_id: str | None) -> None:
        self._selected_feature_id = feature_id
        self.update()

    def _center_and_radius(self) -> tuple[QPointF, float]:
        side = min(self.width(), self.height()) - 2 * _MARGIN
        radius = max(10.0, side / 2)
        center = QPointF(self.width() / 2, self.height() / 2)
        return center, radius

    def _position_to_angle_degrees(self, position0: int, length: int) -> float:
        fraction = position0 / max(length, 1)
        return -90.0 + fraction * 360.0

    def _angle_to_position(self, angle_degrees: float, length: int) -> int:
        normalized = (angle_degrees + 90.0) % 360.0
        return int(round(normalized / 360.0 * length)) % max(length, 1)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), self.palette().base())

        if self._record is None or self._record.length == 0:
            painter.setPen(QPen(QColor("#888888")))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No record loaded")
            painter.end()
            return

        center, radius = self._center_and_radius()
        length = self._record.length

        backbone_rect = QRectF(center.x() - radius, center.y() - radius, 2 * radius, 2 * radius)
        painter.setPen(QPen(QColor("#555555"), 2))
        painter.drawEllipse(backbone_rect)

        origin_point = self._point_on_ring(center, radius, -90.0)
        painter.setPen(QPen(QColor("#111111"), 2))
        painter.drawLine(center, origin_point)

        for feature in self._features:
            self._draw_feature_arc(painter, center, radius, feature, length)

        painter.setPen(QPen(QColor("#333333")))
        painter.drawText(
            QRectF(center.x() - radius, center.y() - 10, 2 * radius, 20),
            Qt.AlignmentFlag.AlignCenter,
            f"{self._record.display_id}  ({length:,} bp, {self._record.topology.value})",
        )
        painter.end()

    def _point_on_ring(self, center: QPointF, radius: float, angle_degrees: float) -> QPointF:
        radians = math.radians(angle_degrees)
        return QPointF(
            center.x() + radius * math.cos(radians), center.y() + radius * math.sin(radians)
        )

    def _draw_feature_arc(
        self, painter: QPainter, center: QPointF, radius: float, feature: Feature, length: int
    ) -> None:
        start_angle = self._position_to_angle_degrees(feature.start0, length)
        end_angle = self._position_to_angle_degrees(feature.end0, length)
        span = end_angle - start_angle
        if span <= 0:
            span += 360.0

        ring_radius = radius + (_RING_WIDTH if feature.strand == -1 else -_RING_WIDTH - _RING_GAP)
        rect = QRectF(
            center.x() - ring_radius, center.y() - ring_radius, 2 * ring_radius, 2 * ring_radius
        )
        color = feature_color(feature.type)
        is_selected = feature.id == self._selected_feature_id
        is_hover = feature.id == self._hover_feature_id
        pen_width = _RING_WIDTH + (4 if is_selected else 0)
        pen_color = (
            QColor("#1f2937") if is_selected else (color.lighter(130) if is_hover else color)
        )
        pen = QPen(pen_color, pen_width)
        pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        painter.setPen(pen)
        # QPainter angles are in 1/16th of a degree, counter-clockwise from 3 o'clock.
        painter.drawArc(rect, int(-start_angle * 16), int(-span * 16))

    def _feature_at_point(self, x: float, y: float) -> Feature | None:
        if self._record is None or self._record.length == 0:
            return None
        center, radius = self._center_and_radius()
        dx, dy = x - center.x(), y - center.y()
        distance = math.hypot(dx, dy)
        angle = math.degrees(math.atan2(dy, dx))
        length = self._record.length

        for feature in self._features:
            ring_radius = radius + (
                _RING_WIDTH if feature.strand == -1 else -_RING_WIDTH - _RING_GAP
            )
            if abs(distance - ring_radius) > _RING_WIDTH / 2 + 2:
                continue
            position0 = self._angle_to_position(angle, length)
            start0, end0 = feature.start0, feature.end0
            if start0 <= end0:
                if start0 <= position0 < end0:
                    return feature
            elif position0 >= start0 or position0 < end0:
                return feature
        return None

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton:
            return
        feature = self._feature_at_point(event.position().x(), event.position().y())
        if feature is not None:
            self._selected_feature_id = feature.id
            self.featureClicked.emit(feature.id)
            self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        feature = self._feature_at_point(event.position().x(), event.position().y())
        new_hover = feature.id if feature is not None else None
        if new_hover != self._hover_feature_id:
            self._hover_feature_id = new_hover
            self.update()
        if feature is not None:
            start_disp, end_disp = display_from_internal(feature.start0, feature.end0)
            strand_map: dict[int | None, str] = {1: "+", -1: "-"}
            strand_text = strand_map.get(feature.strand, "?")
            tooltip = (
                f"{feature.computed_label()}\n{feature.type}  "
                f"{start_disp}..{end_disp}  strand {strand_text}"
            )
            QToolTip.showText(event.globalPosition().toPoint(), tooltip, self)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        feature = self._feature_at_point(event.position().x(), event.position().y())
        if feature is not None:
            self.featureDoubleClicked.emit(feature.id)
