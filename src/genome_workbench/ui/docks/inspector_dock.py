"""Right dock: record summary or an editable feature form.

Editing happens in place here — no separate modal dialog is needed to change
a feature's coordinates, strand, type, or common qualifiers.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
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
    QVBoxLayout,
    QWidget,
)

from genome_workbench.domain.coordinates import display_from_internal
from genome_workbench.domain.locations import LocationOperator, LocationPart, extract_sequence
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

        self._qualifier_edits: dict[str, QLineEdit] = {
            key: QLineEdit() for key in _COMMON_QUALIFIER_KEYS
        }

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
        form.addRow("Start (1-based inclusive)", self._start_spin)
        form.addRow("End (1-based inclusive)", self._end_spin)
        for key, edit in self._qualifier_edits.items():
            form.addRow(f"/{key}", edit)
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
        return widget

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
        for key, edit in self._qualifier_edits.items():
            edit.setText(feature.qualifiers.get_first(key) or "")
        self._provenance_label.setText(feature.provenance_id or "Manual / Imported")
        self._refresh_preview()

    def _current_strand_value(self) -> int | None:
        text = self._strand_combo.currentText()
        return {"+": 1, "-": -1}.get(text)

    def _refresh_preview(self) -> None:
        if self._feature is None or self._record is None:
            return
        try:
            start0, end0 = self._start_spin.value() - 1, self._end_spin.value()
            if end0 <= start0:
                self._validation_label.setText("End must be after start.")
                return
            part = LocationPart(start0=start0, end0=end0, order_index=0)
            strand = self._current_strand_value()
            nucleotide = extract_sequence(
                self._record.sequence, [part], strand, self._record.length
            )
        except Exception as exc:  # noqa: BLE001 - surfaced to the user
            self._validation_label.setText(f"Error: {exc}")
            return

        self._nucleotide_preview.setPlainText(nucleotide[:2000])
        if self._type_edit.text() == "CDS":
            protein = translate(nucleotide).protein
            self._translation_preview.setPlainText(protein[:2000])
        else:
            self._translation_preview.setPlainText("")

        candidate = self._build_candidate_feature()
        issues = validate_feature(candidate, self._record)
        if not issues:
            self._validation_label.setText("No issues.")
        else:
            self._validation_label.setText(
                "\n".join(f"[{issue.severity.upper()}] {issue.message}" for issue in issues)
            )

    def _build_candidate_feature(self) -> Feature:
        assert self._feature is not None
        start0, end0 = self._start_spin.value() - 1, self._end_spin.value()
        qualifiers = QualifierSet()
        for key, edit in self._qualifier_edits.items():
            if edit.text():
                qualifiers.add(key, edit.text())
        for key, values in self._feature.qualifiers.items():
            if key not in _COMMON_QUALIFIER_KEYS:
                qualifiers.set_all(key, values)
        return Feature(
            id=self._feature.id,
            record_id=self._feature.record_id,
            type=self._type_edit.text() or self._feature.type,
            strand=self._current_strand_value(),
            location_operator=LocationOperator.SIMPLE,
            parts=[LocationPart(start0=start0, end0=end0, order_index=0)],
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
        self.featureUpdateRequested.emit(self._feature, after)

    def _on_revert(self) -> None:
        if self._feature is not None:
            self._populate_form(self._feature)
