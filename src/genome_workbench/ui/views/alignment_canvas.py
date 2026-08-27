"""Multiple sequence alignment visualization widget.

Same viewport-driven approach as GenomeCanvas: only the columns and rows
actually on screen are painted, and per-cell coloring is skipped entirely
below a pixels-per-column threshold (mirroring GenomeCanvas's LOD levels),
so this stays smooth regardless of how many sequences or columns the
alignment has -- an alignment with 500 rows x 20,000 columns costs the same
per frame as one with 5 rows x 200 columns, because only the visible
rectangle is ever touched.

Cells are colored by residue identity and dimmed when they match the
column's consensus (see ui/rendering/nucleotide_colors.py::cell_color), so
differences between sequences are visible at a glance without a separate
"diff mode". A conservation bar above the sequence rows summarizes the same
signal across the whole visible range even when zoomed out too far to see
individual residues.
"""

from __future__ import annotations

from PySide6.QtCore import QRect, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPalette,
    QPen,
    QResizeEvent,
    QWheelEvent,
)
from PySide6.QtWidgets import QWidget

from genome_workbench.domain.alignment_analysis import consensus_sequence, conservation_scores
from genome_workbench.domain.models import Alignment, AlignmentSequence, MoleculeType
from genome_workbench.ui.rendering.nucleotide_colors import cell_color
from genome_workbench.ui.rendering.viewport_transform import ViewportTransform

_RULER_HEIGHT = 24
_CONSENSUS_ROW_HEIGHT = 20
_CONSERVATION_BAR_HEIGHT = 18
_ROW_HEIGHT = 18
_LABEL_GUTTER_WIDTH = 140
_SHOW_CELLS_MIN_PX = 2.0
_SHOW_LETTERS_MIN_PX = 8.0


class AlignmentCanvas(QWidget):
    viewportChanged = Signal(int, int)  # view_start0, view_end0 (columns)
    columnClicked = Signal(int)  # 0-based column index

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(160)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._alignment: Alignment | None = None
        self._sequences: list[AlignmentSequence] = []
        self._consensus: str = ""
        self._conservation: list[float] = []
        self._viewport: ViewportTransform | None = None
        self._first_visible_row = 0
        self._color_overrides: dict[str, str] = {}
        self._mono_font = QFont("Consolas", 10)

    # -- Public API --------------------------------------------------------

    def set_alignment(
        self, alignment: Alignment | None, sequences: list[AlignmentSequence]
    ) -> None:
        self._alignment = alignment
        self._sequences = sequences
        self._first_visible_row = 0
        if alignment is not None and alignment.length > 0:
            rows = [s.sequence for s in sequences]
            self._consensus = consensus_sequence(rows)
            self._conservation = conservation_scores(rows, self._consensus)
            self._viewport = ViewportTransform.whole_genome(
                alignment.length, self._column_area_width()
            )
        else:
            self._consensus = ""
            self._conservation = []
            self._viewport = None
        self.update()

    def set_color_overrides(self, overrides: dict[str, str]) -> None:
        self._color_overrides = overrides
        self.update()

    def zoom_to_whole_alignment(self) -> None:
        if self._alignment is None:
            return
        self._viewport = ViewportTransform.whole_genome(
            self._alignment.length, self._column_area_width()
        )
        self._emit_viewport_changed()
        self.update()

    def set_viewport(self, start0: int, end0: int) -> None:
        if self._viewport is None:
            return
        self._viewport = ViewportTransform(
            start0, end0, self._column_area_width(), self._viewport.sequence_length
        )
        self._emit_viewport_changed()
        self.update()

    @property
    def viewport_transform(self) -> ViewportTransform | None:
        return self._viewport

    @property
    def total_row_count(self) -> int:
        return len(self._sequences)

    @property
    def visible_row_count(self) -> int:
        return max(0, (self.height() - self._row_area_top()) // _ROW_HEIGHT)

    @property
    def first_visible_row(self) -> int:
        return self._first_visible_row

    def set_first_visible_row(self, row: int) -> None:
        max_first = max(0, self.total_row_count - 1)
        self._first_visible_row = max(0, min(row, max_first))
        self.update()

    # -- Layout helpers ------------------------------------------------------

    def _column_area_width(self) -> int:
        return max(1, self.width() - _LABEL_GUTTER_WIDTH)

    def _row_area_top(self) -> int:
        return _RULER_HEIGHT + _CONSENSUS_ROW_HEIGHT + _CONSERVATION_BAR_HEIGHT

    def _emit_viewport_changed(self) -> None:
        if self._viewport is not None:
            self.viewportChanged.emit(self._viewport.view_start0, self._viewport.view_end0)

    def _fg_color(self) -> QColor:
        return self.palette().color(QPalette.ColorRole.Text)

    def _muted_color(self) -> QColor:
        return self.palette().color(QPalette.ColorRole.PlaceholderText)

    def _molecule_type(self) -> MoleculeType:
        return self._alignment.molecule_type if self._alignment is not None else MoleculeType.DNA

    # -- Painting --------------------------------------------------------------

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), self.palette().base())
        if self._alignment is None or self._viewport is None:
            painter.setPen(QPen(self._muted_color()))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No alignment loaded")
            painter.end()
            return

        painter.fillRect(
            QRect(0, 0, _LABEL_GUTTER_WIDTH, self.height()),
            self.palette().color(QPalette.ColorRole.AlternateBase),
        )
        self._paint_ruler(painter)
        self._paint_consensus_row(painter)
        self._paint_conservation_bar(painter)
        self._paint_sequence_rows(painter)
        painter.setPen(QPen(self._muted_color()))
        painter.drawLine(_LABEL_GUTTER_WIDTH, 0, _LABEL_GUTTER_WIDTH, self.height())
        painter.end()

    def _paint_ruler(self, painter: QPainter) -> None:
        assert self._viewport is not None
        vt = self._viewport
        painter.setPen(QPen(self._fg_color()))
        painter.drawLine(_LABEL_GUTTER_WIDTH, _RULER_HEIGHT, self.width(), _RULER_HEIGHT)

        target_ticks = max(2, self._column_area_width() // 100)
        raw_step = max(1, vt.visible_length // target_ticks)
        step = _round_to_nice(raw_step)
        first_tick = (vt.view_start0 // step) * step
        painter.setFont(QFont("Segoe UI", 8))
        pos = first_tick
        while pos <= vt.view_end0:
            if pos >= vt.view_start0:
                x = _LABEL_GUTTER_WIDTH + vt.genome_to_pixel(pos)
                painter.drawLine(int(x), _RULER_HEIGHT - 5, int(x), _RULER_HEIGHT)
                painter.drawText(int(x) + 2, _RULER_HEIGHT - 8, f"{pos + 1:,}")
            pos += step

    def _paint_consensus_row(self, painter: QPainter) -> None:
        assert self._viewport is not None
        top = _RULER_HEIGHT
        painter.setPen(QPen(self._fg_color()))
        painter.drawText(4, top + _CONSENSUS_ROW_HEIGHT - 5, "Consensus")
        self._paint_row(painter, top, self._consensus, is_consensus_row=True)

    def _paint_conservation_bar(self, painter: QPainter) -> None:
        """One bar per screen pixel column showing how variable that stretch
        of the alignment is (taller/redder = less conserved), aggregated
        from the precomputed per-column scores so this stays O(visible
        width) regardless of how many columns are actually on screen."""
        assert self._viewport is not None
        vt = self._viewport
        top = _RULER_HEIGHT + _CONSENSUS_ROW_HEIGHT
        bottom = top + _CONSERVATION_BAR_HEIGHT
        painter.setPen(QPen(self._muted_color()))
        painter.drawLine(_LABEL_GUTTER_WIDTH, bottom, self.width(), bottom)
        if not self._conservation:
            return

        width = self._column_area_width()
        painter.setPen(Qt.PenStyle.NoPen)
        for px in range(width):
            col_start = vt.pixel_to_genome(px)
            col_end = max(col_start + 1, vt.pixel_to_genome(px + 1))
            col_end = min(col_end, len(self._conservation))
            if col_start >= col_end:
                continue
            variability = 1.0 - min(self._conservation[col_start:col_end])
            if variability <= 0.0:
                continue
            bar_height = round(_CONSERVATION_BAR_HEIGHT * variability)
            painter.setBrush(QColor.fromHsvF(0.0, min(1.0, 0.3 + variability * 0.7), 0.85))
            painter.drawRect(_LABEL_GUTTER_WIDTH + px, bottom - bar_height, 1, bar_height)

    def _paint_sequence_rows(self, painter: QPainter) -> None:
        top = self._row_area_top()
        visible = self._sequences[
            self._first_visible_row : self._first_visible_row + self.visible_row_count
        ]
        fm = QFontMetrics(self.font())
        for i, seq in enumerate(visible):
            row_top = top + i * _ROW_HEIGHT
            painter.setPen(QPen(self._fg_color()))
            label = seq.label
            if fm.horizontalAdvance(label) > _LABEL_GUTTER_WIDTH - 8:
                label = fm.elidedText(label, Qt.TextElideMode.ElideRight, _LABEL_GUTTER_WIDTH - 8)
            painter.drawText(4, row_top + _ROW_HEIGHT - 5, label)
            self._paint_row(painter, row_top, seq.sequence, is_consensus_row=False)

    def _paint_row(
        self, painter: QPainter, top: int, sequence: str, is_consensus_row: bool
    ) -> None:
        assert self._viewport is not None
        vt = self._viewport
        px_per_col = vt.pixels_per_bp
        if px_per_col < _SHOW_CELLS_MIN_PX or not sequence:
            return
        molecule_type = self._molecule_type()
        show_letters = px_per_col >= _SHOW_LETTERS_MIN_PX
        if show_letters:
            painter.setFont(self._mono_font)
        start = max(0, vt.view_start0)
        end = min(vt.view_end0, len(sequence))
        for col in range(start, end):
            x = _LABEL_GUTTER_WIDTH + vt.genome_to_pixel(col)
            if x < _LABEL_GUTTER_WIDTH - px_per_col or x > self.width():
                continue
            residue = sequence[col]
            is_match = (
                not is_consensus_row
                and col < len(self._consensus)
                and residue.upper() == self._consensus[col]
            )
            color = cell_color(residue, is_match, molecule_type, self._color_overrides)
            painter.fillRect(
                QRect(int(x), top, max(1, round(px_per_col) + 1), _ROW_HEIGHT - 2), color
            )
            if show_letters:
                painter.setPen(
                    QPen(QColor("#1a1a1a") if color.lightnessF() > 0.55 else QColor("white"))
                )
                painter.drawText(
                    QRect(int(x), top, round(px_per_col), _ROW_HEIGHT - 2),
                    Qt.AlignmentFlag.AlignCenter,
                    residue,
                )

    # -- Mouse / wheel interaction --------------------------------------------

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        if self._viewport is None:
            return
        delta = event.angleDelta().y()
        if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            pan_bp = int(self._viewport.visible_length * 0.15) * (-1 if delta > 0 else 1)
            self._viewport = self._viewport.panned(pan_bp)
        else:
            factor = 0.8 if delta > 0 else 1.25
            anchor_x = event.position().x() - _LABEL_GUTTER_WIDTH
            self._viewport = self._viewport.zoomed(factor, anchor_x)
        self._emit_viewport_changed()
        self.update()
        event.accept()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._viewport is None or event.button() != Qt.MouseButton.LeftButton:
            return
        x = event.position().x() - _LABEL_GUTTER_WIDTH
        if x < 0:
            return
        column = self._viewport.pixel_to_genome(x)
        self.columnClicked.emit(column)

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        if self._viewport is not None:
            self._viewport = ViewportTransform(
                self._viewport.view_start0,
                self._viewport.view_end0,
                self._column_area_width(),
                self._viewport.sequence_length,
            )
        super().resizeEvent(event)


def _round_to_nice(value: int) -> int:
    if value <= 0:
        return 1
    magnitude = 10 ** (len(str(value)) - 1)
    for base in (1, 2, 5, 10):
        candidate = base * magnitude
        if candidate >= value:
            return candidate
    return 10 * magnitude
