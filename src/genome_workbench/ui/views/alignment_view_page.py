"""Composite "Alignment View" tab: toolbar + zoomable canvas + vertical
scrollbar (for alignments with more rows than fit on screen) + coordinate
readout. Same shape as GenomeMapPage: the canvas stays a plain, easily
testable widget and this page wires it up with the surrounding chrome.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QScrollBar, QVBoxLayout, QWidget

from genome_workbench.domain.models import Alignment, AlignmentSequence
from genome_workbench.ui.views.alignment_canvas import AlignmentCanvas


class AlignmentViewPage(QWidget):
    featureClicked = Signal(str)  # AlignmentFeature id

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.canvas = AlignmentCanvas(self)
        self._row_scrollbar = QScrollBar()
        self._row_scrollbar.valueChanged.connect(self.canvas.set_first_visible_row)
        self._column_scrollbar = QScrollBar(Qt.Orientation.Horizontal, self)
        self._column_scrollbar.valueChanged.connect(self._on_column_scrollbar_moved)

        zoom_in_button = QPushButton("Zoom In")
        zoom_out_button = QPushButton("Zoom Out")
        fit_button = QPushButton("Fit Whole Alignment")
        self._coordinate_label = QLabel("")

        toolbar = QHBoxLayout()
        toolbar.addWidget(zoom_in_button)
        toolbar.addWidget(zoom_out_button)
        toolbar.addWidget(fit_button)
        toolbar.addStretch()
        toolbar.addWidget(self._coordinate_label)

        canvas_row = QHBoxLayout()
        canvas_row.addWidget(self.canvas, stretch=1)
        canvas_row.addWidget(self._row_scrollbar)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addLayout(toolbar)
        layout.addLayout(canvas_row)
        layout.addWidget(self._column_scrollbar)

        zoom_in_button.clicked.connect(lambda: self._zoom_by(0.6))
        zoom_out_button.clicked.connect(lambda: self._zoom_by(1.6))
        fit_button.clicked.connect(self._on_fit)
        self.canvas.viewportChanged.connect(self._on_viewport_changed)
        self.canvas.columnClicked.connect(self._on_column_clicked)
        self.canvas.featureClicked.connect(self.featureClicked)
        self._sync_scrollbar()
        self._sync_column_scrollbar()

    def set_alignment(
        self, alignment: Alignment | None, sequences: list[AlignmentSequence]
    ) -> None:
        self.canvas.set_alignment(alignment, sequences)
        self._sync_scrollbar()
        self._sync_column_scrollbar()
        self._update_coordinate_label()

    def scroll_to_row(self, row_index: int) -> None:
        """Routed through the scrollbar (rather than canvas.set_first_visible_row
        directly) so its thumb position stays in sync -- it's the only
        listener that currently drives row scrolling."""
        self._row_scrollbar.setValue(row_index)

    def _on_fit(self) -> None:
        # zoom_to_whole_alignment() emits viewportChanged synchronously,
        # which _on_viewport_changed handles below (scrollbar + label).
        self.canvas.zoom_to_whole_alignment()

    def _zoom_by(self, factor: float) -> None:
        vt = self.canvas.viewport_transform
        if vt is None:
            return
        zoomed = vt.zoomed(factor, vt.pixel_width / 2)
        self.canvas.set_viewport(zoomed.view_start0, zoomed.view_end0)

    def _sync_scrollbar(self) -> None:
        total = self.canvas.total_row_count
        visible = self.canvas.visible_row_count
        max_first = max(0, total - visible)
        self._row_scrollbar.setRange(0, max_first)
        self._row_scrollbar.setPageStep(max(1, visible))
        self._row_scrollbar.setEnabled(max_first > 0)

    def _sync_column_scrollbar(self) -> None:
        """Mirrors GenomeMapPage's _sync_scrollbar: reacts to whatever
        changed the viewport (wheel zoom/pan on the canvas, the toolbar
        buttons, or a newly loaded alignment) rather than causing one, so
        its own valueChanged signal is blocked while updating."""
        vt = self.canvas.viewport_transform
        self._column_scrollbar.blockSignals(True)
        if vt is None:
            self._column_scrollbar.setRange(0, 0)
            self._column_scrollbar.setEnabled(False)
        else:
            visible_length = max(1, vt.visible_length)
            max_start = max(0, vt.sequence_length - visible_length)
            self._column_scrollbar.setRange(0, max_start)
            self._column_scrollbar.setPageStep(visible_length)
            self._column_scrollbar.setSingleStep(max(1, visible_length // 20))
            self._column_scrollbar.setValue(vt.view_start0)
            self._column_scrollbar.setEnabled(max_start > 0)
        self._column_scrollbar.blockSignals(False)

    def _on_column_scrollbar_moved(self, value: int) -> None:
        vt = self.canvas.viewport_transform
        if vt is None:
            return
        self.canvas.set_viewport(value, value + vt.visible_length)

    def _on_viewport_changed(self, start0: int, end0: int) -> None:
        self._sync_column_scrollbar()
        self._update_coordinate_label()

    def _on_column_clicked(self, column: int) -> None:
        self._update_coordinate_label(clicked_column=column)

    def _update_coordinate_label(self, clicked_column: int | None = None) -> None:
        vt = self.canvas.viewport_transform
        if vt is None:
            self._coordinate_label.setText("")
            return
        text = f"Columns: {vt.view_start0 + 1:,}..{vt.view_end0:,} ({vt.visible_length:,})"
        if clicked_column is not None:
            text += f"   |   Selected column: {clicked_column + 1:,}"
        self._coordinate_label.setText(text)
