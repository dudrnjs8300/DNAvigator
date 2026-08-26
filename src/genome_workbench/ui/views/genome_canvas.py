"""The central genome visualization widget.

A single continuously-zoomable canvas: at genome scale it shows a density
overview, zooming in reveals colored strand-aware feature arrows, then
labels, then literal nucleotide letters with coordinate ruler, complement
strand, and CDS translation — all in one view (no separate "sequence" vs
"map" tab to switch between). This is the direct replacement for the old
QPlainTextEdit-based sequence view and text-only overview tab.
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPalette,
    QPen,
    QPolygon,
    QResizeEvent,
    QWheelEvent,
)
from PySide6.QtWidgets import QToolTip, QWidget

from genome_workbench.domain.coordinates import display_from_internal
from genome_workbench.domain.models import Feature, SequenceRecord
from genome_workbench.domain.sequence_ops import reverse_complement, translate
from genome_workbench.ui.rendering.feature_colors import feature_color
from genome_workbench.ui.rendering.feature_interval_index import FeatureIntervalIndex
from genome_workbench.ui.rendering.viewport_transform import LodLevel, ViewportTransform

_RULER_HEIGHT = 24
_LANE_HEIGHT = 20
_LANE_GAP = 4
_BASE_ROW_HEIGHT = 18
_EDGE_GRAB_PX = 5


class GenomeCanvas(QWidget):
    featureClicked = Signal(str)
    featureDoubleClicked = Signal(str)
    selectionChanged = Signal(int, int)  # start0, end0; (-1, -1) means cleared
    viewportChanged = Signal(int, int)  # view_start0, view_end0
    contextMenuRequestedAt = Signal(QPoint, int, int)  # global pos, start0, end0
    featureBoundaryEditRequested = Signal(str, int, int)  # feature_id, new_start0, new_end0

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setMinimumHeight(160)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._record: SequenceRecord | None = None
        self._features: list[Feature] = []
        self._index = FeatureIntervalIndex()
        self._viewport: ViewportTransform | None = None

        self._selection: tuple[int, int] | None = None
        self._selected_feature_id: str | None = None
        self._hover_feature_id: str | None = None

        self._drag_mode: str | None = None  # None | "select" | "resize_start" | "resize_end"
        self._drag_anchor_genome: int = 0
        self._resize_feature: Feature | None = None

        self._mono_font = QFont("Consolas", 10)

    # -- Public API --------------------------------------------------------

    def set_record(self, record: SequenceRecord | None, features: list[Feature]) -> None:
        self._record = record
        self._features = features
        self._index.rebuild(features)
        self._selection = None
        self._selected_feature_id = None
        self._hover_feature_id = None
        if record is not None:
            self._viewport = ViewportTransform.whole_genome(max(record.length, 1), self.width())
        else:
            self._viewport = None
        self.update()

    def set_features(self, features: list[Feature]) -> None:
        self._features = features
        self._index.rebuild(features)
        self.update()

    def zoom_to_whole_genome(self) -> None:
        if self._record is None:
            return
        self._viewport = ViewportTransform.whole_genome(max(self._record.length, 1), self.width())
        self._emit_viewport_changed()
        self.update()

    def zoom_to_range(self, start0: int, end0: int, padding_fraction: float = 0.15) -> None:
        if self._viewport is None:
            return
        self._viewport = self._viewport.fit_to_range(start0, end0, padding_fraction)
        self._emit_viewport_changed()
        self.update()

    def zoom_to_feature(self, feature_id: str) -> None:
        feature = self._find_feature(feature_id)
        if feature is not None:
            self.zoom_to_range(feature.start0, feature.end0)

    def zoom_to_selection(self) -> None:
        if self._selection is not None:
            self.zoom_to_range(*self._selection)

    def set_viewport(self, start0: int, end0: int) -> None:
        if self._viewport is None:
            return
        self._viewport = ViewportTransform(
            start0, end0, self.width(), self._viewport.sequence_length
        )
        self._emit_viewport_changed()
        self.update()

    def select_feature(self, feature_id: str | None) -> None:
        self._selected_feature_id = feature_id
        self.update()

    def current_selection(self) -> tuple[int, int] | None:
        return self._selection

    def clear_selection(self) -> None:
        self._selection = None
        self.selectionChanged.emit(-1, -1)
        self.update()

    @property
    def viewport_transform(self) -> ViewportTransform | None:
        return self._viewport

    # -- Internal helpers ----------------------------------------------------

    def _find_feature(self, feature_id: str) -> Feature | None:
        for feature in self._features:
            if feature.id == feature_id:
                return feature
        return None

    def _emit_viewport_changed(self) -> None:
        if self._viewport is not None:
            self.viewportChanged.emit(self._viewport.view_start0, self._viewport.view_end0)

    def _lane_area_top(self) -> int:
        return _RULER_HEIGHT

    def _feature_at_pixel(self, x: int, y: int) -> Feature | None:
        if self._viewport is None:
            return None
        lanes = self._assign_lanes()
        row = (y - self._lane_area_top()) // (_LANE_HEIGHT + _LANE_GAP)
        if row < 0:
            return None
        for feature, lane in lanes:
            if lane != row:
                continue
            x0 = self._viewport.genome_to_pixel(feature.start0)
            x1 = self._viewport.genome_to_pixel(feature.end0)
            if min(x0, x1) - 2 <= x <= max(x0, x1) + 2:
                return feature
        return None

    def _assign_lanes(self) -> list[tuple[Feature, int]]:
        if self._viewport is None:
            return []
        visible = self._index.query_overlapping(
            self._viewport.view_start0, self._viewport.view_end0
        )
        visible.sort(key=lambda f: f.start0)
        lane_ends: list[int] = []
        result: list[tuple[Feature, int]] = []
        for feature in visible:
            placed = False
            for lane_idx, end in enumerate(lane_ends):
                if feature.start0 >= end:
                    lane_ends[lane_idx] = feature.end0
                    result.append((feature, lane_idx))
                    placed = True
                    break
            if not placed:
                lane_ends.append(feature.end0)
                result.append((feature, len(lane_ends) - 1))
        return result

    # -- Painting --------------------------------------------------------------

    def _fg_color(self) -> QColor:
        """Primary foreground color, paired with the palette().base() fill so
        ruler/text stays legible under both light and dark themes."""
        return self.palette().color(QPalette.ColorRole.Text)

    def _muted_color(self) -> QColor:
        return self.palette().color(QPalette.ColorRole.PlaceholderText)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.fillRect(self.rect(), self.palette().base())
        if self._record is None or self._viewport is None:
            painter.setPen(QPen(self._muted_color()))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No record loaded")
            painter.end()
            return

        lod = self._viewport.lod_level()
        self._paint_ruler(painter)
        if lod == LodLevel.OVERVIEW:
            self._paint_density(painter)
        else:
            self._paint_feature_lanes(painter, with_labels=(lod != LodLevel.GENE))
        if lod == LodLevel.BASE:
            self._paint_base_level(painter)
        self._paint_selection(painter)
        painter.end()

    def _paint_ruler(self, painter: QPainter) -> None:
        assert self._viewport is not None
        vt = self._viewport
        painter.setPen(QPen(self._fg_color()))
        painter.drawLine(0, _RULER_HEIGHT, self.width(), _RULER_HEIGHT)

        target_ticks = max(2, self.width() // 120)
        raw_step = max(1, vt.visible_length // target_ticks)
        step = _round_to_nice(raw_step)
        first_tick = (vt.view_start0 // step) * step
        painter.setFont(QFont("Segoe UI", 8))
        pos = first_tick
        while pos <= vt.view_end0:
            if pos >= vt.view_start0:
                x = vt.genome_to_pixel(pos)
                painter.drawLine(int(x), _RULER_HEIGHT - 5, int(x), _RULER_HEIGHT)
                label = f"{pos + 1:,}"
                painter.drawText(int(x) + 2, _RULER_HEIGHT - 8, label)
            pos += step

    def _paint_density(self, painter: QPainter) -> None:
        assert self._viewport is not None
        vt = self._viewport
        y = self._lane_area_top() + 10
        painter.setPen(QPen(self._muted_color()))
        painter.drawLine(0, y, self.width(), y)

        bucket_count = max(1, self.width() // 3)
        bucket_size = max(1, vt.visible_length // bucket_count)
        counts: list[int] = [0] * bucket_count
        for feature in self._index.query_overlapping(vt.view_start0, vt.view_end0):
            mid = (feature.start0 + feature.end0) // 2
            bucket = min(bucket_count - 1, max(0, (mid - vt.view_start0) // bucket_size))
            counts[bucket] += 1
        max_count = max(counts, default=0) or 1

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#3b82c4"))
        for i, count in enumerate(counts):
            if count == 0:
                continue
            bar_height = round(40 * count / max_count)
            x = i * 3
            painter.drawRect(x, y - bar_height, 3, bar_height)

    def _paint_feature_lanes(self, painter: QPainter, with_labels: bool) -> None:
        assert self._viewport is not None
        vt = self._viewport
        lanes = self._assign_lanes()
        fm = QFontMetrics(self.font())
        for feature, lane in lanes:
            top = self._lane_area_top() + lane * (_LANE_HEIGHT + _LANE_GAP) + 4
            x0 = vt.genome_to_pixel(feature.start0)
            x1 = vt.genome_to_pixel(feature.end0)
            left, right = (x0, x1) if x0 <= x1 else (x1, x0)
            left = max(-10, left)
            right = min(self.width() + 10, right)
            if right <= left:
                continue
            color = feature_color(feature.type)
            is_selected = feature.id == self._selected_feature_id
            is_hover = feature.id == self._hover_feature_id
            painter.setPen(
                QPen(
                    self.palette().color(QPalette.ColorRole.Highlight)
                    if is_selected
                    else color.darker(140),
                    2 if is_selected else 1,
                )
            )
            painter.setBrush(color.lighter(120) if is_hover else color)
            _draw_strand_arrow(painter, left, top, right, _LANE_HEIGHT - 4, feature.strand)

            if with_labels:
                label = feature.computed_label()
                text_width = fm.horizontalAdvance(label)
                if text_width <= (right - left) - 4:
                    painter.setPen(QPen(QColor("white")))
                    painter.drawText(
                        QRect(int(left), int(top), int(right - left), _LANE_HEIGHT - 4),
                        Qt.AlignmentFlag.AlignCenter,
                        label,
                    )

    def _paint_base_level(self, painter: QPainter) -> None:
        assert self._viewport is not None and self._record is not None
        vt = self._viewport
        fm = QFontMetrics(self._mono_font)
        char_width = fm.horizontalAdvance("A")
        if char_width <= 0:
            return
        base_area_top = self.height() - (_BASE_ROW_HEIGHT * 3) - 4
        painter.setFont(self._mono_font)

        sequence = self._record.sequence
        start = vt.view_start0
        end = min(vt.view_end0, len(sequence))
        painter.setPen(QPen(self._fg_color()))
        for pos in range(start, end):
            x = vt.genome_to_pixel(pos)
            if x < -char_width or x > self.width():
                continue
            base = sequence[pos]
            painter.drawText(int(x), base_area_top + _BASE_ROW_HEIGHT, base)
            complement_base = reverse_complement(base)
            painter.setPen(QPen(self._muted_color()))
            painter.drawText(int(x), base_area_top + 2 * _BASE_ROW_HEIGHT, complement_base)
            painter.setPen(QPen(self._fg_color()))

        self._paint_translation_overlay(painter, base_area_top, char_width)

    def _paint_translation_overlay(
        self, painter: QPainter, base_area_top: int, char_width: int
    ) -> None:
        """Draw amino-acid letters above the codons of any single-part, plus-strand
        CDS feature overlapping the visible range. Compound/reverse-strand CDS
        translation overlay is deferred (still available via Inspector/preview)."""
        assert self._viewport is not None and self._record is not None
        vt = self._viewport
        cds_features = [
            f
            for f in self._index.query_overlapping(vt.view_start0, vt.view_end0)
            if f.type == "CDS" and len(f.parts) == 1 and f.strand == 1
        ]
        if not cds_features:
            return
        painter.setPen(QPen(QColor("#a8321f")))
        for feature in cds_features:
            part = feature.parts[0]
            nucleotide = self._record.sequence[part.start0 : part.end0]
            offset = (feature.phase or 0) if feature.phase in (0, 1, 2) else 0
            protein = translate(
                nucleotide, codon_start_offset=offset, trim_trailing_stop=False
            ).protein
            for i, residue in enumerate(protein):
                codon_start0 = part.start0 + offset + i * 3
                codon_mid0 = codon_start0 + 1
                if not (vt.view_start0 <= codon_mid0 < vt.view_end0):
                    continue
                x = vt.genome_to_pixel(codon_mid0) - char_width / 2
                painter.drawText(int(x), base_area_top - 4, residue)

    def _paint_selection(self, painter: QPainter) -> None:
        if self._selection is None or self._viewport is None:
            return
        vt = self._viewport
        start0, end0 = self._selection
        x0 = vt.genome_to_pixel(start0)
        x1 = vt.genome_to_pixel(end0)
        left, right = min(x0, x1), max(x0, x1)
        overlay = QColor(59, 130, 196, 60)
        painter.fillRect(
            QRect(int(left), _RULER_HEIGHT, int(right - left), self.height() - _RULER_HEIGHT),
            overlay,
        )
        painter.setPen(QPen(QColor("#1f5fa8"), 1, Qt.PenStyle.DashLine))
        painter.drawLine(int(left), _RULER_HEIGHT, int(left), self.height())
        painter.drawLine(int(right), _RULER_HEIGHT, int(right), self.height())

    # -- Mouse interaction -------------------------------------------------------

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        if self._viewport is None:
            return
        delta = event.angleDelta().y()
        if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            pan_bp = int(self._viewport.visible_length * 0.15) * (-1 if delta > 0 else 1)
            self._viewport = self._viewport.panned(pan_bp)
        else:
            factor = 0.8 if delta > 0 else 1.25
            anchor_x = event.position().x()
            self._viewport = self._viewport.zoomed(factor, anchor_x)
        self._emit_viewport_changed()
        self.update()
        event.accept()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._viewport is None or event.button() != Qt.MouseButton.LeftButton:
            return
        x, y = event.position().x(), event.position().y()
        handle = self._hit_test_resize_handle(x, y)
        if handle is not None:
            feature, which = handle
            self._drag_mode = which
            self._resize_feature = feature
            return

        clicked_feature = self._feature_at_pixel(int(x), int(y))
        if clicked_feature is not None:
            self._selected_feature_id = clicked_feature.id
            self.featureClicked.emit(clicked_feature.id)
            self.update()
            return

        self._drag_mode = "select"
        self._drag_anchor_genome = self._viewport.pixel_to_genome(x)
        self._selection = (self._drag_anchor_genome, self._drag_anchor_genome)
        self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._viewport is None:
            return
        x, y = event.position().x(), event.position().y()

        if self._drag_mode == "select":
            current = self._viewport.pixel_to_genome(x)
            start0, end0 = sorted((self._drag_anchor_genome, current))
            self._selection = (start0, end0)
            self.update()
            return
        if self._drag_mode in ("resize_start", "resize_end") and self._resize_feature is not None:
            self.update()
            return

        feature = self._feature_at_pixel(int(x), int(y))
        new_hover = feature.id if feature is not None else None
        if new_hover != self._hover_feature_id:
            self._hover_feature_id = new_hover
            self.update()
        if feature is not None:
            start_disp, end_disp = display_from_internal(feature.start0, feature.end0)
            strand_map: dict[int | None, str] = {1: "+", -1: "-"}
            strand_text = strand_map.get(feature.strand, "?")
            tooltip = (
                f"{feature.computed_label()}\n{feature.type}  {start_disp}..{end_disp}  "
                f"strand {strand_text}\n{feature.qualifiers.get_first('product') or ''}"
            )
            QToolTip.showText(event.globalPosition().toPoint(), tooltip, self)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._drag_mode == "select" and self._selection is not None:
            start0, end0 = self._selection
            if end0 > start0:
                self.selectionChanged.emit(start0, end0)
            else:
                self._selection = None
                self.selectionChanged.emit(-1, -1)
            self.update()
        elif self._drag_mode in ("resize_start", "resize_end") and self._resize_feature is not None:
            x = event.position().x()
            assert self._viewport is not None
            new_pos = self._viewport.pixel_to_genome(x)
            feature = self._resize_feature
            new_start, new_end = feature.start0, feature.end0
            if self._drag_mode == "resize_start":
                new_start = min(new_pos, feature.end0 - 1)
            else:
                new_end = max(new_pos, feature.start0 + 1)
            if (new_start, new_end) != (feature.start0, feature.end0):
                self.featureBoundaryEditRequested.emit(feature.id, new_start, new_end)
        self._drag_mode = None
        self._resize_feature = None

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        x, y = event.position().x(), event.position().y()
        feature = self._feature_at_pixel(int(x), int(y))
        if feature is not None:
            self.featureDoubleClicked.emit(feature.id)

    def contextMenuEvent(self, event) -> None:  # noqa: N802
        if self._selection is not None:
            start0, end0 = self._selection
        elif self._viewport is not None:
            pos = self._viewport.pixel_to_genome(event.pos().x())
            start0, end0 = pos, min(pos + 1, self._viewport.sequence_length)
        else:
            return
        self.contextMenuRequestedAt.emit(event.globalPos(), start0, end0)

    def _hit_test_resize_handle(self, x: float, y: float) -> tuple[Feature, str] | None:
        if self._selected_feature_id is None or self._viewport is None:
            return None
        feature = self._find_feature(self._selected_feature_id)
        if feature is None:
            return None
        lanes = self._assign_lanes()
        lane = next((lane_idx for feat, lane_idx in lanes if feat.id == feature.id), None)
        if lane is None:
            return None
        top = self._lane_area_top() + lane * (_LANE_HEIGHT + _LANE_GAP) + 4
        if not (top <= y <= top + _LANE_HEIGHT - 4):
            return None
        x0 = self._viewport.genome_to_pixel(feature.start0)
        x1 = self._viewport.genome_to_pixel(feature.end0)
        left, right = min(x0, x1), max(x0, x1)
        if abs(x - left) <= _EDGE_GRAB_PX:
            return feature, "resize_start"
        if abs(x - right) <= _EDGE_GRAB_PX:
            return feature, "resize_end"
        return None

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        if self._viewport is not None:
            self._viewport = ViewportTransform(
                self._viewport.view_start0,
                self._viewport.view_end0,
                self.width(),
                self._viewport.sequence_length,
            )
        super().resizeEvent(event)

    # -- Selection helpers exposed to the controller --------------------------

    def selected_sequence(self) -> str | None:
        if self._record is None or self._selection is None:
            return None
        start0, end0 = self._selection
        return self._record.sequence[start0:end0]

    def selected_translation(self, genetic_code: int = 11) -> str | None:
        seq = self.selected_sequence()
        if seq is None:
            return None
        return translate(seq, genetic_code=genetic_code).protein


def _draw_strand_arrow(
    painter: QPainter, left: float, top: float, right: float, height: float, strand: int | None
) -> None:
    tip = min(10.0, max(0.0, right - left))
    if strand == -1:
        points = [
            QPoint(int(left + tip), int(top)),
            QPoint(int(right), int(top)),
            QPoint(int(right), int(top + height)),
            QPoint(int(left + tip), int(top + height)),
            QPoint(int(left), int(top + height / 2)),
        ]
    elif strand == 1:
        points = [
            QPoint(int(left), int(top)),
            QPoint(int(right - tip), int(top)),
            QPoint(int(right), int(top + height / 2)),
            QPoint(int(right - tip), int(top + height)),
            QPoint(int(left), int(top + height)),
        ]
    else:
        points = [
            QPoint(int(left), int(top)),
            QPoint(int(right), int(top)),
            QPoint(int(right), int(top + height)),
            QPoint(int(left), int(top + height)),
        ]
    painter.drawPolygon(QPolygon(points))


def _round_to_nice(value: int) -> int:
    for base in (1, 2, 5):
        for magnitude in (1, 10, 100, 1_000, 10_000, 100_000, 1_000_000, 10_000_000):
            candidate = base * magnitude
            if candidate >= value:
                return candidate
    return value
