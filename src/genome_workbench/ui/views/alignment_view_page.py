"""Composite "Alignment View" tab: toolbar + zoomable canvas + vertical
scrollbar (for alignments with more rows than fit on screen) + coordinate
readout. Same shape as GenomeMapPage: the canvas stays a plain, easily
testable widget and this page wires it up with the surrounding chrome.
"""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QScrollBar, QVBoxLayout, QWidget

from genome_workbench.domain.models import Alignment, AlignmentSequence
from genome_workbench.ui.views.alignment_canvas import AlignmentCanvas


class AlignmentViewPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.canvas = AlignmentCanvas(self)
        self._row_scrollbar = QScrollBar()
        self._row_scrollbar.valueChanged.connect(self.canvas.set_first_visible_row)

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

        zoom_in_button.clicked.connect(lambda: self._zoom_by(0.6))
        zoom_out_button.clicked.connect(lambda: self._zoom_by(1.6))
        fit_button.clicked.connect(self._on_fit)
        self.canvas.viewportChanged.connect(self._on_viewport_changed)
        self.canvas.columnClicked.connect(self._on_column_clicked)

    def set_alignment(
        self, alignment: Alignment | None, sequences: list[AlignmentSequence]
    ) -> None:
        self.canvas.set_alignment(alignment, sequences)
        self._sync_scrollbar()
        self._update_coordinate_label()

    def _on_fit(self) -> None:
        self.canvas.zoom_to_whole_alignment()
        self._update_coordinate_label()

    def _zoom_by(self, factor: float) -> None:
        vt = self.canvas.viewport_transform
        if vt is None:
            return
        zoomed = vt.zoomed(factor, vt.pixel_width / 2)
        self.canvas.set_viewport(zoomed.view_start0, zoomed.view_end0)
        self._update_coordinate_label()

    def _sync_scrollbar(self) -> None:
        total = self.canvas.total_row_count
        visible = self.canvas.visible_row_count
        max_first = max(0, total - visible)
        self._row_scrollbar.setRange(0, max_first)
        self._row_scrollbar.setPageStep(max(1, visible))
        self._row_scrollbar.setEnabled(max_first > 0)

    def _on_viewport_changed(self, start0: int, end0: int) -> None:
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
