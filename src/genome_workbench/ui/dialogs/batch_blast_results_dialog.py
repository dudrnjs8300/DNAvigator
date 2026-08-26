"""Shows the results of a batch BLAST run (one search per selected feature)
and lets the user review+apply hits one feature at a time -- reuses
ApplyBlastHitDialog so applying still requires the same explicit
preview-before-apply confirmation as a single BLAST search (spec 11.9: never
auto-apply a hit).
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from genome_workbench.application.annotation_service import AnnotationService
from genome_workbench.application.blast_service import BlastService
from genome_workbench.domain.blast_models import BlastSearchResult
from genome_workbench.domain.models import Feature, SequenceRecord
from genome_workbench.ui.dialogs.apply_blast_hit_dialog import ApplyBlastHitDialog

_COLUMNS = ["Feature", "Hits", "Best Subject", "Identity %", "Coverage %", "E-value"]


class BatchBlastResultsDialog(QDialog):
    def __init__(
        self,
        results: list[tuple[str, BlastSearchResult]],
        features_by_id: dict[str, Feature],
        target_record: SequenceRecord,
        blast_service: BlastService,
        annotation_service: AnnotationService,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Batch BLAST Results")
        self.resize(700, 400)
        self._results: dict[str, BlastSearchResult] = dict(results)
        self._features_by_id = features_by_id
        self._target_record = target_record
        self._blast_service = blast_service
        self._annotation_service = annotation_service
        self.applied_feature_ids: set[str] = set()

        self._table = QTableWidget(len(results), len(_COLUMNS))
        self._table.setHorizontalHeaderLabels(_COLUMNS)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        for row, (feature_id, result) in enumerate(results):
            self._populate_row(row, feature_id, result)

        apply_button = QPushButton("Review && Apply Selected...")
        apply_button.clicked.connect(self._on_apply_selected)
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        buttons = QHBoxLayout()
        buttons.addWidget(apply_button)
        buttons.addStretch()
        buttons.addWidget(close_button)

        layout = QVBoxLayout(self)
        layout.addWidget(self._table, stretch=1)
        layout.addLayout(buttons)

    def _populate_row(self, row: int, feature_id: str, result: BlastSearchResult) -> None:
        feature = self._features_by_id.get(feature_id)
        label = feature.computed_label() if feature is not None else feature_id
        best_hit = result.hits[0] if result.hits else None

        name_item = QTableWidgetItem(label)
        name_item.setData(Qt.ItemDataRole.UserRole, feature_id)
        self._table.setItem(row, 0, name_item)
        self._table.setItem(row, 1, QTableWidgetItem(str(len(result.hits))))
        if best_hit is not None:
            self._table.setItem(row, 2, QTableWidgetItem(best_hit.subject_id))
            self._table.setItem(row, 3, QTableWidgetItem(f"{best_hit.best_identity:.1f}"))
            self._table.setItem(row, 4, QTableWidgetItem(f"{best_hit.best_query_coverage:.1f}"))
            self._table.setItem(row, 5, QTableWidgetItem(f"{best_hit.best_evalue:.2e}"))
        else:
            for col in range(2, 6):
                self._table.setItem(row, col, QTableWidgetItem("--"))

    def _on_apply_selected(self) -> None:
        row = self._table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Apply Hit", "Select a row first.")
            return
        name_item = self._table.item(row, 0)
        if name_item is None:
            return
        feature_id = name_item.data(Qt.ItemDataRole.UserRole)
        result = self._results.get(feature_id)
        if result is None or not result.hits or not result.hits[0].hsps:
            QMessageBox.information(self, "Apply Hit", "This feature has no BLAST hits.")
            return
        hit = result.hits[0]
        hsp = hit.hsps[0]
        dialog = ApplyBlastHitDialog(self._target_record, result, hit, hsp, self)
        if not dialog.exec():
            return
        self._blast_service.apply_hit_as_annotation(
            self._annotation_service,
            self._target_record,
            result,
            hit,
            hsp,
            dialog.feature_type(),
            dialog.build_qualifiers(),
        )
        self.applied_feature_ids.add(feature_id)
        name_item.setText(f"{name_item.text()} [applied]")
