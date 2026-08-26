"""Find features by gene name or other qualifier text (Ctrl+F).

Non-modal so the user can keep it open, adjust the query, and jump between
several matches without reopening it each time. Search is scoped to the whole
project (every record), not just the currently displayed one, since a common
Geneious-style workflow is "which contig has gene X" without knowing in
advance which record to look in.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHeaderView,
    QLabel,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from genome_workbench.application.project_service import ProjectService
from genome_workbench.domain.coordinates import display_from_internal
from genome_workbench.domain.models import Feature

_RECORD_ID_ROLE = Qt.ItemDataRole.UserRole
_FEATURE_ID_ROLE = Qt.ItemDataRole.UserRole + 1


def _feature_matches(feature: Feature, needle: str) -> bool:
    haystacks = [feature.type, feature.computed_label(), feature.display_label]
    for _key, values in feature.qualifiers.items():
        haystacks.extend(values)
    return any(needle in (h or "").lower() for h in haystacks)


class FindFeatureDialog(QDialog):
    featureChosen = Signal(str, str)  # record_id, feature_id

    def __init__(self, project_service: ProjectService, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Find Feature")
        self.setModal(False)
        self.resize(640, 420)
        self._project_service = project_service

        self._query_edit = QLineEdit(self)
        self._query_edit.setPlaceholderText(
            "Search gene name, locus_tag, product, note, or any qualifier value..."
        )
        self._query_edit.textChanged.connect(self._run_search)
        self._query_edit.returnPressed.connect(self._activate_first_row)

        self._status_label = QLabel("", self)

        self._results = QTableWidget(0, 4, self)
        self._results.setHorizontalHeaderLabels(["Record", "Type", "Label", "Location"])
        self._results.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._results.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._results.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._results.verticalHeader().setVisible(False)
        self._results.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._results.doubleClicked.connect(
            lambda _index: self._activate_row(self._results.currentRow())
        )

        layout = QVBoxLayout(self)
        layout.addWidget(self._query_edit)
        layout.addWidget(self._status_label)
        layout.addWidget(self._results, stretch=1)

    def open_for_search(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()
        self._query_edit.setFocus()
        self._query_edit.selectAll()
        self._run_search(self._query_edit.text())

    def _run_search(self, text: str) -> None:
        self._results.setRowCount(0)
        needle = text.strip().lower()
        if not needle or not self._project_service.is_open:
            self._status_label.setText("")
            return

        matches: list[tuple[str, str, Feature]] = []
        for record in self._project_service.list_records():
            for feature in self._project_service.list_features(record.id):
                if _feature_matches(feature, needle):
                    matches.append((record.id, record.display_id, feature))

        self._status_label.setText(f"{len(matches)} match(es)")
        self._results.setRowCount(len(matches))
        for row, (record_id, record_label, feature) in enumerate(matches):
            start_disp, end_disp = display_from_internal(feature.start0, feature.end0)
            strand_map: dict[int | None, str] = {1: "+", -1: "-"}
            strand_text = strand_map.get(feature.strand, "?")
            location = f"{start_disp:,}..{end_disp:,} ({strand_text})"

            record_item = QTableWidgetItem(record_label)
            record_item.setData(_RECORD_ID_ROLE, record_id)
            record_item.setData(_FEATURE_ID_ROLE, feature.id)
            self._results.setItem(row, 0, record_item)
            self._results.setItem(row, 1, QTableWidgetItem(feature.type))
            self._results.setItem(row, 2, QTableWidgetItem(feature.computed_label()))
            self._results.setItem(row, 3, QTableWidgetItem(location))

        if matches:
            self._results.selectRow(0)

    def _activate_first_row(self) -> None:
        if self._results.rowCount() > 0:
            self._activate_row(0)

    def _activate_row(self, row: int) -> None:
        if row < 0 or row >= self._results.rowCount():
            return
        item = self._results.item(row, 0)
        if item is None:
            return
        record_id = item.data(_RECORD_ID_ROLE)
        feature_id = item.data(_FEATURE_ID_ROLE)
        if record_id and feature_id:
            self.featureChosen.emit(record_id, feature_id)
