"""Find-in-Alignment (Ctrl+F while the Alignment View tab is active).

Searches two independent things in one box, since "find a sequence" is
ambiguous for an alignment: a sequence *motif* (a DNA/protein pattern, found
against each row's own ungapped bases so a gap padded into the middle of a
match by another row's insertion doesn't break it) and a sequence *label*
(e.g. an isolate name). Both kinds of hits are listed together; picking one
jumps the Alignment View to it.
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

from genome_workbench.domain.alignment_analysis import ungapped_range_to_aligned_columns
from genome_workbench.domain.models import AlignmentSequence

_SEQUENCE_ID_ROLE = Qt.ItemDataRole.UserRole
_COL_START_ROLE = Qt.ItemDataRole.UserRole + 1
_COL_END_ROLE = Qt.ItemDataRole.UserRole + 2

_GAP_CHARS = frozenset("-.")


def _find_motif_matches(sequence: str, needle: str) -> list[tuple[int, int]]:
    """Returns [(ungapped_start, ungapped_end), ...] for every occurrence of
    needle in this row's own ungapped bases (case-insensitive)."""
    ungapped = "".join(ch for ch in sequence if ch not in _GAP_CHARS).upper()
    needle = needle.upper()
    matches = []
    start = 0
    while True:
        index = ungapped.find(needle, start)
        if index == -1:
            break
        matches.append((index, index + len(needle)))
        start = index + 1
    return matches


class FindInAlignmentDialog(QDialog):
    resultChosen = Signal(str, int, int)  # alignment_sequence_id, col_start, col_end

    def __init__(self, sequences: list[AlignmentSequence], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Find in Alignment")
        self.setModal(False)
        self.resize(560, 400)
        self._sequences = sequences

        self._query_edit = QLineEdit(self)
        self._query_edit.setPlaceholderText(
            "Search a sequence motif (e.g. ATCGGT) or a sequence name..."
        )
        self._query_edit.textChanged.connect(self._run_search)
        self._query_edit.returnPressed.connect(self._activate_first_row)

        self._status_label = QLabel("", self)

        self._results = QTableWidget(0, 3, self)
        self._results.setHorizontalHeaderLabels(["Sequence", "Match", "Position"])
        self._results.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._results.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._results.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._results.verticalHeader().setVisible(False)
        self._results.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
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
        needle = text.strip()
        if not needle:
            self._status_label.setText("")
            return

        rows: list[tuple[str, str, str, str, int, int]] = []
        needle_lower = needle.lower()
        for seq in self._sequences:
            if needle_lower in seq.label.lower():
                rows.append((seq.id, seq.label, "name", "whole sequence", 0, len(seq.sequence)))
            for ungapped_start, ungapped_end in _find_motif_matches(seq.sequence, needle):
                col_start, col_end = ungapped_range_to_aligned_columns(
                    seq.sequence, ungapped_start, ungapped_end
                )
                rows.append(
                    (
                        seq.id,
                        seq.label,
                        "motif",
                        f"cols {col_start + 1:,}..{col_end:,}",
                        col_start,
                        col_end,
                    )
                )

        self._status_label.setText(f"{len(rows)} match(es)")
        self._results.setRowCount(len(rows))
        for row_index, (seq_id, label, kind, position_text, col_start, col_end) in enumerate(rows):
            label_item = QTableWidgetItem(label)
            label_item.setData(_SEQUENCE_ID_ROLE, seq_id)
            label_item.setData(_COL_START_ROLE, col_start)
            label_item.setData(_COL_END_ROLE, col_end)
            self._results.setItem(row_index, 0, label_item)
            self._results.setItem(row_index, 1, QTableWidgetItem(kind))
            self._results.setItem(row_index, 2, QTableWidgetItem(position_text))

        if rows:
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
        seq_id = item.data(_SEQUENCE_ID_ROLE)
        col_start = item.data(_COL_START_ROLE)
        col_end = item.data(_COL_END_ROLE)
        if seq_id:
            self.resultChosen.emit(seq_id, col_start, col_end)
