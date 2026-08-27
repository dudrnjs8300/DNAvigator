"""Feature table: sortable list of features for the current record.

Also the entry point for batch operations: selecting multiple rows (Ctrl/
Shift-click) and right-clicking offers "Batch Edit Qualifiers..." and
"Apply Template..." so several features can be edited in one action instead
of one at a time through the Inspector.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent, QKeySequence
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QMenu,
    QTableWidget,
    QTableWidgetItem,
)

from genome_workbench.domain.coordinates import display_from_internal
from genome_workbench.domain.models import Feature

_COLUMNS = ["Label", "Type", "Start", "End", "Strand", "Length", "Gene", "Product"]


class FeatureTableView(QTableWidget):
    featureSelected = Signal(str)  # feature id
    batchEditQualifiersRequested = Signal(list)  # list[str] feature ids
    applyTemplateRequested = Signal(list)  # list[str] feature ids
    batchBlastRequested = Signal(list)  # list[str] feature ids

    def __init__(self, parent=None) -> None:
        super().__init__(0, len(_COLUMNS), parent)
        self.setHorizontalHeaderLabels(_COLUMNS)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSortingEnabled(True)
        self.itemSelectionChanged.connect(self._on_selection_changed)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_context_menu)

    def set_features(self, features: list[Feature]) -> None:
        self.setSortingEnabled(False)
        self.setRowCount(0)
        for feature in features:
            row = self.rowCount()
            self.insertRow(row)
            start_display, end_display = display_from_internal(feature.start0, feature.end0)
            strand_map: dict[int | None, str] = {1: "+", -1: "-", 0: "?"}
            strand_text = strand_map.get(feature.strand, "?")
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

    def select_feature_row(self, feature_id: str) -> None:
        """Programmatically select the row for ``feature_id`` without re-emitting
        featureSelected (avoids a signal feedback loop with the canvas/table sync)."""
        for row in range(self.rowCount()):
            item = self.item(row, 0)
            if item is not None and item.data(Qt.ItemDataRole.UserRole) == feature_id:
                self.blockSignals(True)
                self.selectRow(row)
                self.blockSignals(False)
                self.scrollToItem(item)
                return

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if event.matches(QKeySequence.StandardKey.Copy):
            self._copy_selected_rows_to_clipboard()
            event.accept()
            return
        super().keyPressEvent(event)

    def _copy_selected_rows_to_clipboard(self) -> None:
        rows = sorted({index.row() for index in self.selectedIndexes()})
        if not rows:
            return
        lines = ["\t".join(_COLUMNS)]
        for row in rows:
            values = []
            for col in range(len(_COLUMNS)):
                item = self.item(row, col)
                values.append(item.text() if item is not None else "")
            lines.append("\t".join(values))
        QApplication.clipboard().setText("\n".join(lines))

    def _on_selection_changed(self) -> None:
        rows = {index.row() for index in self.selectedIndexes()}
        if len(rows) == 1:
            row = next(iter(rows))
            item = self.item(row, 0)
            if item is not None:
                feature_id = item.data(Qt.ItemDataRole.UserRole)
                if feature_id:
                    self.featureSelected.emit(feature_id)

    def selected_feature_ids(self) -> list[str]:
        rows = sorted({index.row() for index in self.selectedIndexes()})
        ids = []
        for row in rows:
            item = self.item(row, 0)
            if item is not None:
                feature_id = item.data(Qt.ItemDataRole.UserRole)
                if feature_id:
                    ids.append(feature_id)
        return ids

    def _on_context_menu(self, position) -> None:
        # QMenu.exec() can't be monkeypatched (D-008) -- this method only
        # builds+execs the menu; the actual emit happens right after exec()
        # returns, so tests can call selected_feature_ids() + emit directly
        # instead of driving the popup.
        feature_ids = self.selected_feature_ids()
        if len(feature_ids) < 2:
            return
        menu = QMenu(self)
        batch_edit = menu.addAction(f"Batch Edit Qualifiers... ({len(feature_ids)} selected)")
        apply_template = menu.addAction(f"Apply Template... ({len(feature_ids)} selected)")
        batch_blast = menu.addAction(f"Run BLAST on Selected... ({len(feature_ids)} selected)")
        chosen = menu.exec(self.viewport().mapToGlobal(position))
        if chosen is batch_edit:
            self.batchEditQualifiersRequested.emit(feature_ids)
        elif chosen is apply_template:
            self.applyTemplateRequested.emit(feature_ids)
        elif chosen is batch_blast:
            self.batchBlastRequested.emit(feature_ids)
