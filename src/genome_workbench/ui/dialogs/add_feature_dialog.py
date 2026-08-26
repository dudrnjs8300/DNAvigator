"""Manual feature creation dialog: coordinates, strand, type, common qualifiers, preview."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
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

        self._start_spin = QSpinBox()
        self._start_spin.setRange(1, max(record.length, 1))
        self._start_spin.setValue(initial_start_1based or 1)

        self._end_spin = QSpinBox()
        self._end_spin.setRange(1, max(record.length, 1))
        self._end_spin.setValue(initial_end_1based or min(record.length, 1))

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
        form.addRow("Start (1-based inclusive)", self._start_spin)
        form.addRow("End (1-based inclusive)", self._end_spin)
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

        self._update_preview()

    def _current_strand(self) -> int:
        return 1 if self._strand_combo.currentText() == "+" else -1

    def _update_preview(self) -> None:
        start = self._start_spin.value()
        end = self._end_spin.value()
        if end < start:
            self._preview_text.setPlainText("End must be >= start.")
            return
        try:
            preview = self._annotation_service.preview_simple_feature(
                self._record, start, end, self._current_strand(), self._type_combo.currentText()
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
        start = self._start_spin.value()
        end = self._end_spin.value()
        if end < start:
            return
        qualifiers = QualifierSet()
        if self._gene_edit.text():
            qualifiers.add("gene", self._gene_edit.text())
        if self._product_edit.text():
            qualifiers.add("product", self._product_edit.text())
        if self._note_edit.text():
            qualifiers.add("note", self._note_edit.text())
        if self._transl_table_edit.text():
            qualifiers.add("transl_table", self._transl_table_edit.text())

        self.created_feature = self._annotation_service.create_simple_feature(
            self._record,
            start,
            end,
            self._current_strand(),
            self._type_combo.currentText(),
            qualifiers,
        )
        self.accept()
