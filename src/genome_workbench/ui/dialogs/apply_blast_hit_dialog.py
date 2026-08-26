"""Preview-before-apply dialog for turning a BLAST hit into an annotation
(spec 11.9: never auto-apply the top hit; the user must see mapped
coordinates, metrics, and choose which metadata fields to copy).
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QPlainTextEdit,
    QVBoxLayout,
)

from genome_workbench.domain.blast_models import (
    BlastHit,
    BlastHsp,
    BlastSearchResult,
    map_hsp_to_genome_location,
)
from genome_workbench.domain.coordinates import display_from_internal
from genome_workbench.domain.models import SequenceRecord
from genome_workbench.domain.qualifiers import QualifierSet

_COMMON_TYPES = ["CDS", "misc_feature", "gene"]


class ApplyBlastHitDialog(QDialog):
    def __init__(
        self,
        target_record: SequenceRecord,
        search_result: BlastSearchResult,
        hit: BlastHit,
        hsp: BlastHsp,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Apply BLAST Hit as Annotation")
        self._target_record = target_record
        self._search_result = search_result
        self._hit = hit
        self._hsp = hsp

        genome_start0, genome_end0, genome_strand = map_hsp_to_genome_location(search_result, hsp)
        self._mapped_start0 = genome_start0
        self._mapped_end0 = genome_end0
        self._mapped_strand = genome_strand
        start_disp, end_disp = display_from_internal(genome_start0, genome_end0)

        self._type_combo = QComboBox()
        self._type_combo.setEditable(True)
        self._type_combo.addItems(_COMMON_TYPES)

        self._copy_product_check = QCheckBox("product (from subject title)")
        self._copy_note_check = QCheckBox("note (BLAST evidence summary)")
        self._copy_note_check.setChecked(True)
        self._copy_dbxref_check = QCheckBox("db_xref (subject id)")

        summary = QPlainTextEdit()
        summary.setReadOnly(True)
        summary.setPlainText(
            f"Target record: {target_record.display_id}\n"
            f"Mapped location: {start_disp}..{end_disp} (1-based inclusive)  "
            f"strand {'+' if genome_strand == 1 else '-'}\n"
            f"Subject: {hit.subject_id} — {hit.subject_title}\n"
            f"Identity: {hsp.identity_pct:.1f}%   Query coverage: {hsp.query_coverage_pct:.1f}%\n"
            f"E-value: {hsp.evalue:.2e}   Bit score: {hsp.bitscore:.1f}\n"
            f"Program: {search_result.program.value}   "
            f"Database: {search_result.database_id}"
        )

        form = QFormLayout()
        form.addRow("Feature type", self._type_combo)
        form.addRow(QLabel("Copy from hit:"))
        form.addRow(self._copy_product_check)
        form.addRow(self._copy_note_check)
        form.addRow(self._copy_dbxref_check)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(summary)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def mapped_location(self) -> tuple[int, int, int]:
        return self._mapped_start0, self._mapped_end0, self._mapped_strand

    def feature_type(self) -> str:
        return self._type_combo.currentText() or "misc_feature"

    def build_qualifiers(self) -> QualifierSet:
        qualifiers = QualifierSet()
        if self._copy_product_check.isChecked():
            qualifiers.add("product", self._hit.subject_title)
        if self._copy_note_check.isChecked():
            qualifiers.add(
                "note",
                f"BLAST {self._search_result.program.value} hit vs {self._hit.subject_id}: "
                f"{self._hsp.identity_pct:.1f}% identity, {self._hsp.query_coverage_pct:.1f}% "
                f"coverage, e-value {self._hsp.evalue:.2e}",
            )
        if self._copy_dbxref_check.isChecked():
            qualifiers.add("db_xref", self._hit.subject_id)
        return qualifiers
