"""Composite "Genome Map" tab: toolbar + zoomable canvas + minimap + coordinate readout.

This is the primary screen of the application (spec: the central
visualization is the core of the program, not a table).
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QScrollBar, QVBoxLayout, QWidget

from genome_workbench.domain.models import Feature, SequenceRecord
from genome_workbench.ui.views.genome_canvas import GenomeCanvas
from genome_workbench.ui.widgets.minimap import Minimap


class GenomeMapPage(QWidget):
    featureClicked = Signal(str)
    featureDoubleClicked = Signal(str)
    selectionChanged = Signal(int, int)
    contextMenuRequestedAt = Signal(QPoint, int, int)
    featureBoundaryEditRequested = Signal(str, int, int)
    regionCopied = Signal(str, int, int, int)  # record_id, start0, end0, strand

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.canvas = GenomeCanvas(self)
        self.minimap = Minimap(self)
        self._position_scrollbar = QScrollBar(Qt.Orientation.Horizontal, self)
        self._position_scrollbar.valueChanged.connect(self._on_scrollbar_moved)

        zoom_in_button = QPushButton("Zoom In")
        zoom_out_button = QPushButton("Zoom Out")
        fit_genome_button = QPushButton("Fit Genome")
        zoom_selection_button = QPushButton("Zoom to Selection")
        self._coordinate_label = QLabel("")

        toolbar = QHBoxLayout()
        toolbar.addWidget(zoom_in_button)
        toolbar.addWidget(zoom_out_button)
        toolbar.addWidget(fit_genome_button)
        toolbar.addWidget(zoom_selection_button)
        toolbar.addStretch()
        toolbar.addWidget(self._coordinate_label)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addLayout(toolbar)
        layout.addWidget(self.canvas, stretch=1)
        layout.addWidget(self._position_scrollbar)
        layout.addWidget(self.minimap)

        zoom_in_button.clicked.connect(lambda: self._zoom_by(0.6))
        zoom_out_button.clicked.connect(lambda: self._zoom_by(1.6))
        fit_genome_button.clicked.connect(self.canvas.zoom_to_whole_genome)
        zoom_selection_button.clicked.connect(self.canvas.zoom_to_selection)

        self.canvas.featureClicked.connect(self.featureClicked)
        self.canvas.featureDoubleClicked.connect(self.featureDoubleClicked)
        self.canvas.selectionChanged.connect(self._on_selection_changed)
        self.canvas.contextMenuRequestedAt.connect(self.contextMenuRequestedAt)
        self.canvas.featureBoundaryEditRequested.connect(self.featureBoundaryEditRequested)
        self.canvas.viewportChanged.connect(self._on_viewport_changed)
        self.canvas.regionCopied.connect(self.regionCopied)
        self.minimap.viewportRequested.connect(lambda s, e: self.canvas.set_viewport(s, e))
        self._sync_scrollbar()

    def set_record(self, record: SequenceRecord | None, features: list[Feature]) -> None:
        self.canvas.set_record(record, features)
        self.minimap.set_record_length(record.length if record else 0)
        self.minimap.set_features(features)
        if record is not None and self.canvas.viewport_transform is not None:
            vt = self.canvas.viewport_transform
            self.minimap.set_viewport(vt.view_start0, vt.view_end0)
        self._sync_scrollbar()
        self._update_coordinate_label()

    def set_features(self, features: list[Feature]) -> None:
        self.canvas.set_features(features)
        self.minimap.set_features(features)

    def set_color_overrides(self, overrides: dict[str, str]) -> None:
        self.canvas.set_color_overrides(overrides)
        self.minimap.set_color_overrides(overrides)

    def select_feature(self, feature_id: str | None) -> None:
        self.canvas.select_feature(feature_id)

    def zoom_to_feature(self, feature_id: str) -> None:
        self.canvas.zoom_to_feature(feature_id)

    def _zoom_by(self, factor: float) -> None:
        vt = self.canvas.viewport_transform
        if vt is None:
            return
        zoomed = vt.zoomed(factor, vt.pixel_width / 2)
        self.canvas.set_viewport(zoomed.view_start0, zoomed.view_end0)

    def _on_selection_changed(self, start0: int, end0: int) -> None:
        self.selectionChanged.emit(start0, end0)
        self._update_coordinate_label()

    def _on_viewport_changed(self, start0: int, end0: int) -> None:
        self.minimap.set_viewport(start0, end0)
        self._sync_scrollbar()
        self._update_coordinate_label()

    def _sync_scrollbar(self) -> None:
        """Keeps the horizontal scrollbar's range/page/thumb in lock-step
        with whatever changed the viewport (wheel zoom/pan on the canvas
        itself, the minimap, the toolbar buttons, or a new record) --
        blocking its own signal while doing so, since this is a reaction to
        a viewport change rather than the cause of one."""
        vt = self.canvas.viewport_transform
        self._position_scrollbar.blockSignals(True)
        if vt is None:
            self._position_scrollbar.setRange(0, 0)
            self._position_scrollbar.setEnabled(False)
        else:
            visible_length = max(1, vt.visible_length)
            max_start = max(0, vt.sequence_length - visible_length)
            self._position_scrollbar.setRange(0, max_start)
            self._position_scrollbar.setPageStep(visible_length)
            self._position_scrollbar.setSingleStep(max(1, visible_length // 20))
            self._position_scrollbar.setValue(vt.view_start0)
            self._position_scrollbar.setEnabled(max_start > 0)
        self._position_scrollbar.blockSignals(False)

    def _on_scrollbar_moved(self, value: int) -> None:
        vt = self.canvas.viewport_transform
        if vt is None:
            return
        self.canvas.set_viewport(value, value + vt.visible_length)

    def _update_coordinate_label(self) -> None:
        vt = self.canvas.viewport_transform
        if vt is None:
            self._coordinate_label.setText("")
            return
        text = f"View: {vt.view_start0 + 1:,}..{vt.view_end0:,}  ({vt.visible_length:,} bp)"
        selection = self.canvas.current_selection()
        if selection is not None:
            selection_length = selection[1] - selection[0]
            text += (
                f"   |   Selection: {selection[0] + 1:,}..{selection[1]:,} "
                f"({selection_length:,} bp)"
            )
        self._coordinate_label.setText(text)
