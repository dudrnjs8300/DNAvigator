"""Feature table: sortable list of features for the current record."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QAbstractItemView, QTableWidget, QTableWidgetItem

from genome_workbench.domain.coordinates import display_from_internal
from genome_workbench.domain.models import Feature

_COLUMNS = ["Label", "Type", "Start", "End", "Strand", "Length", "Gene", "Product"]


class FeatureTableView(QTableWidget):
    featureSelected = Signal(str)  # feature id

    def __init__(self, parent=None) -> None:
        super().__init__(0, len(_COLUMNS), parent)
        self.setHorizontalHeaderLabels(_COLUMNS)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSortingEnabled(True)
        self.itemSelectionChanged.connect(self._on_selection_changed)

    def set_features(self, features: list[Feature]) -> None:
        self.setSortingEnabled(False)
        self.setRowCount(0)
        for feature in features:
            row = self.rowCount()
            self.insertRow(row)
            start_display, end_display = display_from_internal(feature.start0, feature.end0)
            strand_text = {1: "+", -1: "-", 0: "?", None: "?"}.get(feature.strand, "?")
            values = [
                feature.computed_label(),
                feature.type,
                str(start_display),
                str(end_display),
                strand_text,
                str(feature.length),
                feature.qualifiers.get_first("gene") or "",
                feature.qualifiers.get_first("product") or "",
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                if col == 0:
                    item.setData(Qt.ItemDataRole.UserRole, feature.id)
                self.setItem(row, col, item)
        self.setSortingEnabled(True)

    def _on_selection_changed(self) -> None:
        rows = {index.row() for index in self.selectedIndexes()}
        if len(rows) == 1:
            row = next(iter(rows))
            item = self.item(row, 0)
            if item is not None:
                feature_id = item.data(Qt.ItemDataRole.UserRole)
                if feature_id:
                    self.featureSelected.emit(feature_id)
