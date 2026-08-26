"""Main application window. Assembles docks/views and wires every enabled
menu action to a real application-service call — no placeholder actions.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QDockWidget,
    QFileDialog,
    QInputDialog,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QTabWidget,
)

from genome_workbench.application.annotation_service import AnnotationService
from genome_workbench.application.export_service import ExportService, ExportValidationError
from genome_workbench.application.import_service import ImportService
from genome_workbench.application.project_service import ProjectService
from genome_workbench.domain.models import Feature, SequenceRecord
from genome_workbench.ui.actions import make_action
from genome_workbench.ui.dialogs.add_feature_dialog import AddFeatureDialog
from genome_workbench.ui.docks.inspector_dock import InspectorDock
from genome_workbench.ui.docks.project_explorer_dock import ProjectExplorerDock
from genome_workbench.ui.views.feature_table_view import FeatureTableView
from genome_workbench.ui.views.sequence_view import SequenceView
from genome_workbench.version import APP_NAME, APP_VERSION

logger = logging.getLogger("genome_workbench.ui")


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} {APP_VERSION}")
        self.resize(1200, 800)

        self.project_service = ProjectService()
        self.import_service = ImportService(self.project_service)
        self.export_service = ExportService(self.project_service)
        self.annotation_service = AnnotationService(self.project_service)

        self._current_record: SequenceRecord | None = None
        self._current_feature: Feature | None = None

        self._build_docks()
        self._build_central_tabs()
        self._build_menus()
        self._update_action_states()
        self.statusBar().showMessage("No project open")

    # -- UI construction -----------------------------------------------------

    def _build_docks(self) -> None:
        self._explorer_dock = ProjectExplorerDock(self)
        self._explorer_dock.recordSelected.connect(self._on_record_selected)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self._explorer_dock)

        self._inspector_dock = InspectorDock(self)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._inspector_dock)

        self._log_dock = QPlainTextEdit(self)
        self._log_dock.setReadOnly(True)
        self._log_dock.setMaximumBlockCount(1000)
        log_wrapper = QDockWidget("Jobs && Log", self)
        log_wrapper.setWidget(self._log_dock)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, log_wrapper)

    def _build_central_tabs(self) -> None:
        self._tabs = QTabWidget(self)

        self._overview_view = QPlainTextEdit(self)
        self._overview_view.setReadOnly(True)
        self._tabs.addTab(self._overview_view, "Overview")

        self._sequence_view = SequenceView(self)
        self._tabs.addTab(self._sequence_view, "Sequence")

        self._feature_table = FeatureTableView(self)
        self._feature_table.featureSelected.connect(self._on_feature_selected)
        self._tabs.addTab(self._feature_table, "Feature Table")

        self.setCentralWidget(self._tabs)

    def _build_menus(self) -> None:
        file_menu = self.menuBar().addMenu("&File")
        self.action_new_project = make_action(self, "&New Project...", self._on_new_project)
        self.action_open_project = make_action(self, "&Open Project...", self._on_open_project)
        self.action_import_fasta = make_action(self, "Import &FASTA...", self._on_import_fasta)
        self.action_import_genbank = make_action(
            self, "Import &GenBank...", self._on_import_genbank
        )
        self.action_save_project = make_action(
            self, "&Save Project", self._on_save_project, shortcut="Ctrl+S"
        )
        self.action_export_genbank = make_action(
            self, "&Export GenBank...", self._on_export_genbank
        )
        self.action_exit = make_action(self, "E&xit", self._on_exit)
        for action in (
            self.action_new_project,
            self.action_open_project,
            None,
            self.action_import_fasta,
            self.action_import_genbank,
            None,
            self.action_save_project,
            self.action_export_genbank,
            None,
            self.action_exit,
        ):
            file_menu.addSeparator() if action is None else file_menu.addAction(action)

        edit_menu = self.menuBar().addMenu("&Edit")
        self.action_undo = make_action(
            self, "&Undo", self._on_undo, shortcut=QKeySequence.StandardKey.Undo
        )
        self.action_redo = make_action(
            self, "&Redo", self._on_redo, shortcut=QKeySequence.StandardKey.Redo
        )
        edit_menu.addAction(self.action_undo)
        edit_menu.addAction(self.action_redo)

        annotation_menu = self.menuBar().addMenu("&Annotation")
        self.action_add_feature = make_action(self, "&Add Feature...", self._on_add_feature)
        annotation_menu.addAction(self.action_add_feature)

        blast_menu = self.menuBar().addMenu("&BLAST")
        blast_setup = make_action(
            self,
            "BLAST Setup...",
            enabled=False,
            tooltip="Phase 5에서 구현 예정 (BLAST+ 설치/등록)",
        )
        blast_run = make_action(
            self,
            "Run BLAST...",
            enabled=False,
            tooltip="Phase 6에서 구현 예정 (BLAST 검색 및 근거 기반 annotation)",
        )
        blast_menu.addAction(blast_setup)
        blast_menu.addAction(blast_run)

        help_menu = self.menuBar().addMenu("&Help")
        help_menu.addAction(make_action(self, "&About", self._on_about))

    # -- State sync -----------------------------------------------------------

    def _log(self, message: str) -> None:
        logger.info(message)
        self._log_dock.appendPlainText(message)

    def _update_action_states(self) -> None:
        is_open = self.project_service.is_open
        has_record = self._current_record is not None
        has_records = is_open and bool(self.project_service.list_records())
        self.action_save_project.setEnabled(is_open)
        self.action_export_genbank.setEnabled(has_records)
        self.action_add_feature.setEnabled(has_record)
        self.action_import_fasta.setEnabled(is_open)
        self.action_import_genbank.setEnabled(is_open)
        self.action_undo.setEnabled(is_open and self.project_service.undo_stack.can_undo)
        self.action_redo.setEnabled(is_open and self.project_service.undo_stack.can_redo)

    def _refresh_project_explorer(self) -> None:
        if not self.project_service.is_open:
            self._explorer_dock.set_records([])
            return
        self._explorer_dock.set_records(self.project_service.list_records())

    def _refresh_current_record_views(self) -> None:
        self._sequence_view.set_record(self._current_record)
        if self._current_record is not None:
            self._inspector_dock.show_record(self._current_record)
            self._feature_table.set_features(
                self.project_service.list_features(self._current_record.id)
            )
            self._overview_view.setPlainText(
                f"Record: {self._current_record.display_id}\n"
                f"Length: {self._current_record.length} bp\n"
                f"Molecule type: {self._current_record.molecule_type.value}\n"
                f"Topology: {self._current_record.topology.value}\n"
                f"Description: {self._current_record.description}"
            )
            self.statusBar().showMessage(
                f"{self._current_record.display_id} — {self._current_record.length} bp"
            )
        else:
            self._inspector_dock.clear()
            self._feature_table.set_features([])
            self._overview_view.setPlainText("")

    # -- Menu handlers ---------------------------------------------------------

    def _on_new_project(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "New Project", "", "GenomeWorkbench Project (*.gwbproj)"
        )
        if not path:
            return
        name, ok = QInputDialog.getText(self, "Project Name", "Name:")
        if not ok:
            return
        try:
            self.project_service.create_new(Path(path), name or "Untitled Project")
        except Exception as exc:  # noqa: BLE001 - shown to user, not swallowed
            QMessageBox.critical(self, "New Project Failed", str(exc))
            return
        self._current_record = None
        self._refresh_project_explorer()
        self._refresh_current_record_views()
        self._update_action_states()
        self._log(f"Created project: {path}")

    def _on_open_project(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Project", "", "GenomeWorkbench Project (*.gwbproj)"
        )
        if not path:
            return
        try:
            self.project_service.open(Path(path))
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Open Project Failed", str(exc))
            return
        self._current_record = None
        self._refresh_project_explorer()
        self._refresh_current_record_views()
        self._update_action_states()
        self._log(f"Opened project: {path}")

    def _on_import_fasta(self) -> None:
        if not self._guard_project_open():
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Import FASTA",
            "",
            "FASTA (*.fasta *.fa *.fna *.ffn *.fnn *.fas *.fsa *.faa *.gz)",
        )
        if not path:
            return
        result = self.import_service.import_fasta(Path(path))
        self._refresh_project_explorer()
        self._update_action_states()
        self._log(f"Imported {len(result.records)} record(s) from {path}")
        for issue in result.issues:
            self._log(f"  [{issue.severity}] {issue.message}")

    def _on_import_genbank(self) -> None:
        if not self._guard_project_open():
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Import GenBank", "", "GenBank (*.gb *.gbk *.genbank *.gbff *.gz)"
        )
        if not path:
            return
        result = self.import_service.import_genbank(Path(path))
        self._refresh_project_explorer()
        self._update_action_states()
        self._log(f"Imported {len(result.records)} record(s) from {path}")
        for issue in result.issues:
            self._log(f"  [{issue.severity}] {issue.message}")

    def _on_save_project(self) -> None:
        if not self._guard_project_open():
            return
        self.project_service.touch()
        self._log("Project saved")

    def _on_export_genbank(self) -> None:
        if not self._guard_project_open():
            return
        records = self.project_service.list_records()
        if not records:
            QMessageBox.information(self, "Export GenBank", "No records to export.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export GenBank", "", "GenBank (*.gbk)")
        if not path:
            return
        features_by_record_id = {
            record.id: self.project_service.list_features(record.id) for record in records
        }
        try:
            result = self.export_service.export_genbank(records, features_by_record_id, Path(path))
        except ExportValidationError as exc:
            QMessageBox.critical(self, "Export Failed Validation", str(exc))
            return
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Export Failed", str(exc))
            return
        self._log(f"Exported {len(records)} record(s) to {result.destination}")
        for warning in result.warnings:
            self._log(f"  [warning] {warning.message}")

    def _on_undo(self) -> None:
        if self.project_service.undo_stack.undo():
            self._refresh_current_record_views()
            self._update_action_states()
            self._log("Undo")

    def _on_redo(self) -> None:
        if self.project_service.undo_stack.redo():
            self._refresh_current_record_views()
            self._update_action_states()
            self._log("Redo")

    def _on_add_feature(self) -> None:
        if self._current_record is None:
            return
        dialog = AddFeatureDialog(self._current_record, self.annotation_service, self)
        if dialog.exec():
            self._refresh_current_record_views()
            self._update_action_states()
            if dialog.created_feature is not None:
                self._log(f"Created feature: {dialog.created_feature.computed_label()}")

    def _on_exit(self) -> None:
        self.close()

    def _on_about(self) -> None:
        QMessageBox.about(
            self,
            f"About {APP_NAME}",
            f"{APP_NAME} {APP_VERSION}\nLocal genome sequence visualization "
            "and annotation workbench.",
        )

    def _on_record_selected(self, record_id: str) -> None:
        record = self.project_service.get_record(record_id)
        self._current_record = record
        self._current_feature = None
        self._refresh_current_record_views()
        self._update_action_states()

    def _on_feature_selected(self, feature_id: str) -> None:
        if self._current_record is None:
            return
        for feature in self.project_service.list_features(self._current_record.id):
            if feature.id == feature_id:
                self._current_feature = feature
                self._inspector_dock.show_feature(feature, self._current_record)
                return

    def _guard_project_open(self) -> bool:
        if not self.project_service.is_open:
            QMessageBox.warning(self, "No Project Open", "Open or create a project first.")
            return False
        return True

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt override signature
        self.project_service.close()
        super().closeEvent(event)
