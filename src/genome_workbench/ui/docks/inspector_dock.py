"""Right dock: record summary or an editable feature form.

Editing happens in place here — no separate modal dialog is needed to change
a feature's coordinates, strand, type, or common qualifiers. Compound (join)
features are edited via the same segments-table pattern as
dialogs/add_feature_dialog.py, and the "Multiple segments (join)" checkbox
is pre-checked from the feature's actual part count on load -- this matters
because before this existed, opening a compound feature here and clicking
Apply silently collapsed it to a single bounding-box segment (the form only
ever built a 1-part SIMPLE feature, regardless of what was selected).
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDockWidget,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from genome_workbench.domain.coordinates import display_from_internal
from genome_workbench.domain.locations import (
    LocationOperator,
    LocationPart,
    build_ordered_parts_from_display_segments,
    extract_sequence,
)
from genome_workbench.domain.models import Feature, SequenceRecord
from genome_workbench.domain.qualifiers import QualifierSet
from genome_workbench.domain.sequence_ops import translate
from genome_workbench.domain.validation import validate_feature

_COMMON_QUALIFIER_KEYS = ["gene", "locus_tag", "product", "note", "db_xref", "inference"]


class InspectorDock(QDockWidget):
    featureUpdateRequested = Signal(object, object)  # before: Feature, after: Feature

    def __init__(self, parent=None) -> None:
        super().__init__("Inspector", parent)
        self._record: SequenceRecord | None = None
        self._feature: Feature | None = None

        self._stack = QStackedWidget()
        self._empty_label = QLabel("Select a record or feature to inspect.")
        self._record_view = QPlainTextEdit()
        self._record_view.setReadOnly(True)
        self._feature_form = self._build_feature_form()

        self._stack.addWidget(self._empty_label)
        self._stack.addWidget(self._record_view)
        self._stack.addWidget(self._feature_form)
        self.setWidget(self._stack)

    def _build_feature_form(self) -> QWidget:
        widget = QWidget()

        self._type_edit = QLineEdit()
        self._strand_combo = QComboBox()
        self._strand_combo.addItems(["+", "-", "unknown"])
        self._start_spin = QSpinBox()
        self._start_spin.setRange(1, 1_000_000_000)
        self._end_spin = QSpinBox()
        self._end_spin.setRange(1, 1_000_000_000)

        self._join_checkbox = QCheckBox("Multiple segments (join)")
        self._join_checkbox.toggled.connect(self._on_join_toggled)

        self._segments_table = QTableWidget(0, 4)
        self._segments_table.setHorizontalHeaderLabels(
            ["Start (1-based)", "End (1-based)", "Fuzzy start (<)", "Fuzzy end (>)"]
        )
        self._segments_table.setMaximumHeight(120)
        self._segments_table.itemChanged.connect(self._refresh_preview)
        add_segment_button = QPushButton("Add Segment")
        remove_segment_button = QPushButton("Remove Selected")
        add_segment_button.clicked.connect(self._on_add_segment)
        remove_segment_button.clicked.connect(self._on_remove_segment)
        segment_buttons = QHBoxLayout()
        segment_buttons.addWidget(add_segment_button)
        segment_buttons.addWidget(remove_segment_button)
        segment_buttons.addStretch()

        self._fuzzy_start_check = QCheckBox("Fuzzy start (<) -- exact start unknown/beyond view")
        self._fuzzy_end_check = QCheckBox("Fuzzy end (>) -- exact end unknown/beyond view")
        self._fuzzy_start_check.toggled.connect(self._refresh_preview)
        self._fuzzy_end_check.toggled.connect(self._refresh_preview)

        self._simple_location_widget = QWidget()
        simple_form = QFormLayout(self._simple_location_widget)
        simple_form.setContentsMargins(0, 0, 0, 0)
        simple_form.addRow("Start (1-based inclusive)", self._start_spin)
        simple_form.addRow("", self._fuzzy_start_check)
        simple_form.addRow("End (1-based inclusive)", self._end_spin)
        simple_form.addRow("", self._fuzzy_end_check)

        self._compound_location_widget = QWidget()
        compound_layout = QVBoxLayout(self._compound_location_widget)
        compound_layout.setContentsMargins(0, 0, 0, 0)
        compound_layout.addWidget(self._segments_table)
        compound_layout.addLayout(segment_buttons)

        self._location_stack = QStackedWidget()
        self._location_stack.addWidget(self._simple_location_widget)
        self._location_stack.addWidget(self._compound_location_widget)

        self._qualifier_edits: dict[str, QLineEdit] = {
            key: QLineEdit() for key in _COMMON_QUALIFIER_KEYS
        }

        self._advanced_qualifier_table = QTableWidget(0, 2)
        self._advanced_qualifier_table.setHorizontalHeaderLabels(["Key", "Value"])
        self._advanced_qualifier_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self._advanced_qualifier_table.setMaximumHeight(140)
        add_row_button = QPushButton("Add Qualifier")
        remove_row_button = QPushButton("Remove Selected")
        add_row_button.clicked.connect(self._on_add_qualifier_row)
        remove_row_button.clicked.connect(self._on_remove_qualifier_row)
        advanced_buttons = QHBoxLayout()
        advanced_buttons.addWidget(add_row_button)
        advanced_buttons.addWidget(remove_row_button)
        advanced_buttons.addStretch()

        self._nucleotide_preview = QPlainTextEdit()
        self._nucleotide_preview.setReadOnly(True)
        self._nucleotide_preview.setMaximumHeight(60)
        self._translation_preview = QPlainTextEdit()
        self._translation_preview.setReadOnly(True)
        self._translation_preview.setMaximumHeight(60)
        self._validation_label = QLabel("")
        self._validation_label.setWordWrap(True)
        self._provenance_label = QLabel("")

        form = QFormLayout()
        form.addRow("Type", self._type_edit)
        form.addRow("Strand", self._strand_combo)
        form.addRow(self._join_checkbox)
        form.addRow(self._location_stack)
        for key, edit in self._qualifier_edits.items():
            form.addRow(f"/{key}", edit)
        form.addRow(QLabel("All other qualifiers:"))
        form.addRow(self._advanced_qualifier_table)
        form.addRow(advanced_buttons)
        form.addRow("Nucleotide", self._nucleotide_preview)
        form.addRow("Translation", self._translation_preview)
        form.addRow("Validation", self._validation_label)
        form.addRow("Provenance", self._provenance_label)

        apply_button = QPushButton("Apply")
        revert_button = QPushButton("Revert")
        apply_button.clicked.connect(self._on_apply)
        revert_button.clicked.connect(self._on_revert)
        buttons = QHBoxLayout()
        buttons.addWidget(apply_button)
        buttons.addWidget(revert_button)
        buttons.addStretch()

        layout = QVBoxLayout(widget)
        layout.addLayout(form)
        layout.addLayout(buttons)
        layout.addStretch()

        for edit in self._qualifier_edits.values():
            edit.textChanged.connect(self._refresh_preview)
        self._type_edit.textChanged.connect(self._refresh_preview)
        self._strand_combo.currentTextChanged.connect(self._refresh_preview)
        self._start_spin.valueChanged.connect(self._refresh_preview)
        self._end_spin.valueChanged.connect(self._refresh_preview)
        self._advanced_qualifier_table.itemChanged.connect(self._refresh_preview)
        return widget

    def _on_add_qualifier_row(self) -> None:
        row = self._advanced_qualifier_table.rowCount()
        self._advanced_qualifier_table.insertRow(row)
        self._advanced_qualifier_table.setItem(row, 0, QTableWidgetItem(""))
        self._advanced_qualifier_table.setItem(row, 1, QTableWidgetItem(""))

    def _on_remove_qualifier_row(self) -> None:
        rows = sorted({index.row() for index in self._advanced_qualifier_table.selectedIndexes()})
        for row in reversed(rows):
            self._advanced_qualifier_table.removeRow(row)
        self._refresh_preview()

    def _on_join_toggled(self, checked: bool) -> None:
        self._location_stack.setCurrentIndex(1 if checked else 0)
        self._refresh_preview()

    @staticmethod
    def _make_checkable_item(checked: bool) -> QTableWidgetItem:
        item = QTableWidgetItem()
        item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
        item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
        return item

    def _add_segment_row(
        self,
        start_1based: int,
        end_1based: int,
        fuzzy_start: bool = False,
        fuzzy_end: bool = False,
    ) -> None:
        row = self._segments_table.rowCount()
        self._segments_table.insertRow(row)
        self._segments_table.setItem(row, 0, QTableWidgetItem(str(start_1based)))
        self._segments_table.setItem(row, 1, QTableWidgetItem(str(end_1based)))
        self._segments_table.setItem(row, 2, self._make_checkable_item(fuzzy_start))
        self._segments_table.setItem(row, 3, self._make_checkable_item(fuzzy_end))

    def _on_add_segment(self) -> None:
        default_end = min(self._record.length, 1) if self._record is not None else 1
        self._add_segment_row(1, default_end)
        self._refresh_preview()

    def _on_remove_segment(self) -> None:
        rows = sorted({index.row() for index in self._segments_table.selectedIndexes()})
        for row in reversed(rows):
            if self._segments_table.rowCount() > 1:
                self._segments_table.removeRow(row)
        self._refresh_preview()

    def _current_segments(self) -> list[tuple[int, int, bool, bool]] | None:
        segments: list[tuple[int, int, bool, bool]] = []
        for row in range(self._segments_table.rowCount()):
            start_item = self._segments_table.item(row, 0)
            end_item = self._segments_table.item(row, 1)
            fuzzy_start_item = self._segments_table.item(row, 2)
            fuzzy_end_item = self._segments_table.item(row, 3)
            try:
                start = int(start_item.text()) if start_item else 0
                end = int(end_item.text()) if end_item else 0
            except ValueError:
                return None
            if start < 1 or end < start:
                return None
            fuzzy_start = bool(
                fuzzy_start_item and fuzzy_start_item.checkState() == Qt.CheckState.Checked
            )
            fuzzy_end = bool(
                fuzzy_end_item and fuzzy_end_item.checkState() == Qt.CheckState.Checked
            )
            segments.append((start, end, fuzzy_start, fuzzy_end))
        return segments or None

    def show_record(self, record: SequenceRecord) -> None:
        self._record = record
        self._feature = None
        lines = [
            f"Record: {record.display_id}",
            f"Name: {record.name}",
            f"Description: {record.description}",
            f"Molecule type: {record.molecule_type.value}",
            f"Topology: {record.topology.value}",
            f"Length: {record.length} bp",
        ]
        self._record_view.setPlainText("\n".join(lines))
        self._stack.setCurrentWidget(self._record_view)

    def show_feature(self, feature: Feature, record: SequenceRecord) -> None:
        self._record = record
        self._feature = feature
        self._start_spin.setMaximum(max(record.length, 1))
        self._end_spin.setMaximum(max(record.length, 1))
        self._populate_form(feature)
        self._stack.setCurrentWidget(self._feature_form)

    def clear(self) -> None:
        self._record = None
        self._feature = None
        self._stack.setCurrentWidget(self._empty_label)

    def _populate_form(self, feature: Feature) -> None:
        # Start/end always seed from the feature's bounding span (Feature.start0/
        # end0 already reduce multi-part locations to min-start/max-end), so
        # they're sensible even if the user unchecks "join" for a compound
        # feature and collapses it to a single segment.
        start_disp, end_disp = display_from_internal(feature.start0, feature.end0)
        self._type_edit.setText(feature.type)
        strand_map: dict[int | None, str] = {1: "+", -1: "-"}
        self._strand_combo.setCurrentText(strand_map.get(feature.strand, "unknown"))
        self._start_spin.blockSignals(True)
        self._end_spin.blockSignals(True)
        self._start_spin.setValue(start_disp)
        self._end_spin.setValue(end_disp)
        self._start_spin.blockSignals(False)
        self._end_spin.blockSignals(False)

        self._fuzzy_start_check.blockSignals(True)
        self._fuzzy_end_check.blockSignals(True)
        # only meaningful for a genuine single-part feature; multi-part
        # features have no single "the" start/end to mark fuzzy here (that's
        # per-segment, handled in the segments table below)
        self._fuzzy_start_check.setChecked(len(feature.parts) == 1 and feature.parts[0].fuzzy_start)
        self._fuzzy_end_check.setChecked(len(feature.parts) == 1 and feature.parts[0].fuzzy_end)
        self._fuzzy_start_check.blockSignals(False)
        self._fuzzy_end_check.blockSignals(False)

        is_join = len(feature.parts) > 1
        self._join_checkbox.blockSignals(True)
        self._join_checkbox.setChecked(is_join)
        self._join_checkbox.blockSignals(False)
        self._location_stack.setCurrentIndex(1 if is_join else 0)

        self._segments_table.blockSignals(True)
        self._segments_table.setRowCount(0)
        # ascending genomic order for readability, regardless of strand or
        # stored order_index -- matches AddFeatureDialog's convention where
        # segment entry order never matters (Apply re-derives order_index).
        for part in sorted(feature.parts, key=lambda p: p.start0):
            part_start_disp, part_end_disp = display_from_internal(part.start0, part.end0)
            self._add_segment_row(part_start_disp, part_end_disp, part.fuzzy_start, part.fuzzy_end)
        self._segments_table.blockSignals(False)

        for key, edit in self._qualifier_edits.items():
            edit.setText(feature.qualifiers.get_first(key) or "")

        self._advanced_qualifier_table.blockSignals(True)
        self._advanced_qualifier_table.setRowCount(0)
        for key, values in feature.qualifiers.items():
            if key in _COMMON_QUALIFIER_KEYS:
                continue
            for value in values:
                row = self._advanced_qualifier_table.rowCount()
                self._advanced_qualifier_table.insertRow(row)
                self._advanced_qualifier_table.setItem(row, 0, QTableWidgetItem(key))
                self._advanced_qualifier_table.setItem(row, 1, QTableWidgetItem(value))
        self._advanced_qualifier_table.blockSignals(False)

        self._provenance_label.setText(feature.provenance_id or "Manual / Imported")
        self._refresh_preview()

    def _current_strand_value(self) -> int | None:
        text = self._strand_combo.currentText()
        return {"+": 1, "-": -1}.get(text)

    def _current_parts_and_operator(self) -> tuple[list[LocationPart], LocationOperator] | None:
        strand = self._current_strand_value()
        if self._join_checkbox.isChecked():
            segments = self._current_segments()
            if not segments:
                return None
            try:
                parts = build_ordered_parts_from_display_segments(segments, strand)
            except ValueError:
                return None
            return parts, LocationOperator.JOIN
        start0, end0 = self._start_spin.value() - 1, self._end_spin.value()
        if end0 <= start0:
            return None
        part = LocationPart(
            start0=start0,
            end0=end0,
            order_index=0,
            fuzzy_start=self._fuzzy_start_check.isChecked(),
            fuzzy_end=self._fuzzy_end_check.isChecked(),
        )
        return [part], LocationOperator.SIMPLE

    def _refresh_preview(self) -> None:
        if self._feature is None or self._record is None:
            return
        candidate = self._build_candidate_feature()
        if candidate is None:
            self._nucleotide_preview.setPlainText("")
            self._translation_preview.setPlainText("")
            self._validation_label.setText(
                "Enter valid segment(s) -- end must be after start in every segment."
            )
            return

        strand = self._current_strand_value()
        try:
            nucleotide = extract_sequence(
                self._record.sequence, candidate.parts, strand, self._record.length
            )
        except Exception as exc:  # noqa: BLE001 - surfaced to the user
            self._validation_label.setText(f"Error: {exc}")
            return

        self._nucleotide_preview.setPlainText(nucleotide[:2000])
        if candidate.type == "CDS":
            protein = translate(nucleotide).protein
            self._translation_preview.setPlainText(protein[:2000])
        else:
            self._translation_preview.setPlainText("")

        issues = validate_feature(candidate, self._record)
        if not issues:
            self._validation_label.setText("No issues.")
        else:
            self._validation_label.setText(
                "\n".join(f"[{issue.severity.upper()}] {issue.message}" for issue in issues)
            )

    def _build_candidate_feature(self) -> Feature | None:
        assert self._feature is not None
        result = self._current_parts_and_operator()
        if result is None:
            return None
        parts, operator = result

        qualifiers = QualifierSet()
        for key, edit in self._qualifier_edits.items():
            if edit.text():
                qualifiers.add(key, edit.text())
        for row in range(self._advanced_qualifier_table.rowCount()):
            key_item = self._advanced_qualifier_table.item(row, 0)
            value_item = self._advanced_qualifier_table.item(row, 1)
            key = key_item.text().strip() if key_item else ""
            value = value_item.text() if value_item else ""
            if key and key not in _COMMON_QUALIFIER_KEYS:
                qualifiers.add(key, value)
        return Feature(
            id=self._feature.id,
            record_id=self._feature.record_id,
            type=self._type_edit.text() or self._feature.type,
            strand=self._current_strand_value(),
            location_operator=operator,
            parts=parts,
            qualifiers=qualifiers,
            display_label=self._feature.display_label,
            parent_ids=list(self._feature.parent_ids),
            child_ids=list(self._feature.child_ids),
            source=self._feature.source,
            score=self._feature.score,
            phase=self._feature.phase,
            provenance_id=self._feature.provenance_id,
            created_at=self._feature.created_at,
            revision=self._feature.revision,
        )

    def _on_apply(self) -> None:
        if self._feature is None:
            return
        after = self._build_candidate_feature()
        if after is None:
            self._validation_label.setText(
                "Cannot apply -- fix the segment(s) first (end must be after start)."
            )
            return
        self.featureUpdateRequested.emit(self._feature, after)

    def _on_revert(self) -> None:
        if self._feature is not None:
            self._populate_form(self._feature)
