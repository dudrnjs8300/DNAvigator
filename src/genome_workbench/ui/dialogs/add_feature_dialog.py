"""Manual feature creation dialog: coordinates, strand, type, common qualifiers, preview.

Supports both a simple single-segment location and a compound (join)
location built from multiple segments, entered in any order — ascending
genomic order is derived automatically, and biological (order_index) order
is computed from strand via AnnotationService (see docs/DECISIONS.md D-002).
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
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

from genome_workbench.application.annotation_service import AnnotationService
from genome_workbench.domain.models import Feature, SequenceRecord
from genome_workbench.domain.qualifiers import QualifierSet
from genome_workbench.domain.validation import Severity

_COMMON_FEATURE_TYPES = [
    "CDS",
    "gene",
    "tRNA",
    "rRNA",
    "misc_feature",
    "repeat_region",
    "promoter",
    "source",
]


class AddFeatureDialog(QDialog):
    def __init__(
        self,
        record: SequenceRecord,
        annotation_service: AnnotationService,
        parent=None,
        initial_start_1based: int | None = None,
        initial_end_1based: int | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Add Feature")
        self._record = record
        self._annotation_service = annotation_service
        self.created_feature: Feature | None = None

        max_length = max(record.length, 1)
        start_value = initial_start_1based or 1
        end_value = initial_end_1based or min(record.length, 1)

        self._start_spin = QSpinBox()
        self._start_spin.setRange(1, max_length)
        self._start_spin.setValue(start_value)
        self._end_spin = QSpinBox()
        self._end_spin.setRange(1, max_length)
        self._end_spin.setValue(end_value)

        self._join_checkbox = QCheckBox("Multiple segments (join)")
        self._join_checkbox.toggled.connect(self._on_join_toggled)

        self._segments_table = QTableWidget(0, 2)
        self._segments_table.setHorizontalHeaderLabels(["Start (1-based)", "End (1-based)"])
        self._segments_table.setMaximumHeight(120)
        add_segment_button = QPushButton("Add Segment")
        remove_segment_button = QPushButton("Remove Selected")
        add_segment_button.clicked.connect(self._on_add_segment)
        remove_segment_button.clicked.connect(self._on_remove_segment)
        segment_buttons = QHBoxLayout()
        segment_buttons.addWidget(add_segment_button)
        segment_buttons.addWidget(remove_segment_button)
        segment_buttons.addStretch()

        self._simple_location_widget = QWidget()
        simple_form = QFormLayout(self._simple_location_widget)
        simple_form.setContentsMargins(0, 0, 0, 0)
        simple_form.addRow("Start (1-based inclusive)", self._start_spin)
        simple_form.addRow("End (1-based inclusive)", self._end_spin)

        self._compound_location_widget = QWidget()
        compound_layout = QVBoxLayout(self._compound_location_widget)
        compound_layout.setContentsMargins(0, 0, 0, 0)
        compound_layout.addWidget(self._segments_table)
        compound_layout.addLayout(segment_buttons)

        self._location_stack = QStackedWidget()
        self._location_stack.addWidget(self._simple_location_widget)
        self._location_stack.addWidget(self._compound_location_widget)

        self._strand_combo = QComboBox()
        self._strand_combo.addItems(["+", "-"])

        self._type_combo = QComboBox()
        self._type_combo.setEditable(True)
        self._type_combo.addItems(_COMMON_FEATURE_TYPES)

        self._gene_edit = QLineEdit()
        self._product_edit = QLineEdit()
        self._note_edit = QLineEdit()
        self._transl_table_edit = QLineEdit("11")

        self._preview_text = QPlainTextEdit()
        self._preview_text.setReadOnly(True)
        self._preview_text.setMaximumHeight(140)

        preview_button = QPushButton("Preview")
        preview_button.clicked.connect(self._update_preview)

        form = QFormLayout()
        form.addRow(self._join_checkbox)
        form.addRow(self._location_stack)
        form.addRow("Strand", self._strand_combo)
        form.addRow("Feature type", self._type_combo)
        form.addRow("gene", self._gene_edit)
        form.addRow("product", self._product_edit)
        form.addRow("note", self._note_edit)
        form.addRow("transl_table", self._transl_table_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(preview_button)
        layout.addWidget(QLabel("Preview:"))
        layout.addWidget(self._preview_text)
        layout.addWidget(buttons)

        self._add_segment_row(start_value, end_value)
        self._update_preview()

    def _on_join_toggled(self, checked: bool) -> None:
        self._location_stack.setCurrentIndex(1 if checked else 0)
        self._update_preview()

    def _add_segment_row(self, start_1based: int, end_1based: int) -> None:
        row = self._segments_table.rowCount()
        self._segments_table.insertRow(row)
        self._segments_table.setItem(row, 0, QTableWidgetItem(str(start_1based)))
        self._segments_table.setItem(row, 1, QTableWidgetItem(str(end_1based)))

    def _on_add_segment(self) -> None:
        self._add_segment_row(1, min(self._record.length, 1))

    def _on_remove_segment(self) -> None:
        rows = sorted({index.row() for index in self._segments_table.selectedIndexes()})
        for row in reversed(rows):
            if self._segments_table.rowCount() > 1:
                self._segments_table.removeRow(row)
        self._update_preview()

    def _current_strand(self) -> int:
        return 1 if self._strand_combo.currentText() == "+" else -1

    def _current_segments(self) -> list[tuple[int, int]] | None:
        segments: list[tuple[int, int]] = []
        for row in range(self._segments_table.rowCount()):
            start_item = self._segments_table.item(row, 0)
            end_item = self._segments_table.item(row, 1)
            try:
                start = int(start_item.text()) if start_item else 0
                end = int(end_item.text()) if end_item else 0
            except ValueError:
                return None
            if start < 1 or end < start:
                return None
            segments.append((start, end))
        return segments or None

    def _is_join_mode(self) -> bool:
        return self._join_checkbox.isChecked()

    def _build_qualifiers(self) -> QualifierSet:
        qualifiers = QualifierSet()
        if self._gene_edit.text():
            qualifiers.add("gene", self._gene_edit.text())
        if self._product_edit.text():
            qualifiers.add("product", self._product_edit.text())
        if self._note_edit.text():
            qualifiers.add("note", self._note_edit.text())
        if self._transl_table_edit.text():
            qualifiers.add("transl_table", self._transl_table_edit.text())
        return qualifiers

    def _update_preview(self) -> None:
        feature_type = self._type_combo.currentText()
        strand = self._current_strand()
        try:
            if self._is_join_mode():
                segments = self._current_segments()
                if not segments:
                    self._preview_text.setPlainText("Enter at least one valid segment.")
                    return
                preview = self._annotation_service.preview_compound_feature(
                    self._record, segments, strand, feature_type
                )
            else:
                start, end = self._start_spin.value(), self._end_spin.value()
                if end < start:
                    self._preview_text.setPlainText("End must be >= start.")
                    return
                preview = self._annotation_service.preview_simple_feature(
                    self._record, start, end, strand, feature_type
                )
        except Exception as exc:  # noqa: BLE001 - surfaced to the user, not swallowed
            self._preview_text.setPlainText(f"Preview failed: {exc}")
            return

        lines = [f"Length: {preview.length} bp"]
        if preview.translation is not None:
            t = preview.translation
            lines.append(f"Translation ({len(t.protein)} aa): {t.protein[:80]}")
            lines.append(f"Start codon present: {t.has_start_codon}")
            lines.append(f"Stop codon present: {t.has_stop_codon}")
            lines.append(f"Internal stop codons: {t.internal_stop_count}")
        if preview.issues:
            lines.append("")
            lines.append("Validation issues:")
            for issue in preview.issues:
                marker = "ERROR" if issue.severity == Severity.ERROR else issue.severity.upper()
                lines.append(f"  [{marker}] {issue.message}")
        self._preview_text.setPlainText("\n".join(lines))

    def _on_accept(self) -> None:
        feature_type = self._type_combo.currentText()
        strand = self._current_strand()
        qualifiers = self._build_qualifiers()

        if self._is_join_mode():
            segments = self._current_segments()
            if not segments:
                return
            self.created_feature = self._annotation_service.create_compound_feature(
                self._record, segments, strand, feature_type, qualifiers
            )
        else:
            start, end = self._start_spin.value(), self._end_spin.value()
            if end < start:
                return
            self.created_feature = self._annotation_service.create_simple_feature(
                self._record, start, end, strand, feature_type, qualifiers
            )
        self.accept()
