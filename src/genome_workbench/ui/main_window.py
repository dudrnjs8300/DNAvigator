"""Main application window.

The central widget is the genome visualization (Genome Map / Circular Map /
Feature Table tabs) — not a text list. Every enabled menu action and canvas
interaction is wired to a real application-service call; nothing here is a
placeholder.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QDockWidget,
    QFileDialog,
    QInputDialog,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QTabWidget,
)

from genome_workbench.application.annotation_service import AnnotationService
from genome_workbench.application.blast_service import BlastService
from genome_workbench.application.export_service import ExportService, ExportValidationError
from genome_workbench.application.import_service import ImportService
from genome_workbench.application.project_service import ProjectService
from genome_workbench.application.sequence_operations_service import SequenceOperationsService
from genome_workbench.domain.blast_models import (
    BlastInstallation,
    BlastSearchResult,
    suggest_program,
)
from genome_workbench.domain.events import EventType
from genome_workbench.domain.locations import LocationPart, extract_sequence
from genome_workbench.domain.models import Feature, SequenceRecord, Topology
from genome_workbench.infrastructure.filesystem.annotation_templates import load_templates
from genome_workbench.infrastructure.filesystem.project_lock import ProjectLockedError
from genome_workbench.ui.actions import make_action
from genome_workbench.ui.dialogs.add_feature_dialog import AddFeatureDialog
from genome_workbench.ui.dialogs.apply_blast_hit_dialog import ApplyBlastHitDialog
from genome_workbench.ui.dialogs.batch_blast_results_dialog import BatchBlastResultsDialog
from genome_workbench.ui.dialogs.batch_qualifier_dialog import BatchQualifierDialog
from genome_workbench.ui.dialogs.blast_setup_dialog import BlastSetupDialog
from genome_workbench.ui.dialogs.create_blast_database_dialog import CreateBlastDatabaseDialog
from genome_workbench.ui.dialogs.find_feature_dialog import FindFeatureDialog
from genome_workbench.ui.docks.blast_panel import BlastPanel
from genome_workbench.ui.docks.inspector_dock import InspectorDock
from genome_workbench.ui.docks.project_explorer_dock import ProjectExplorerDock
from genome_workbench.ui.views.circular_genome_canvas import CircularGenomeCanvas
from genome_workbench.ui.views.feature_table_view import FeatureTableView
from genome_workbench.ui.views.genome_map_page import GenomeMapPage
from genome_workbench.ui.workers.callable_worker import CallableWorker
from genome_workbench.version import APP_NAME, APP_VERSION

logger = logging.getLogger("genome_workbench.ui")


class MainWindow(QMainWindow):
    def __init__(
        self, blast_work_dir: Path | None = None, templates_dir: Path | None = None
    ) -> None:
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} {APP_VERSION}")
        self.resize(1400, 900)

        self.project_service = ProjectService()
        self.import_service = ImportService(self.project_service)
        self.export_service = ExportService(self.project_service)
        self.annotation_service = AnnotationService(self.project_service)
        self.blast_service = BlastService(self.project_service, work_dir=blast_work_dir)
        self.sequence_ops_service = SequenceOperationsService()
        self._templates_dir = templates_dir

        self._current_record: SequenceRecord | None = None
        self._current_feature: Feature | None = None
        self._blast_installation = BlastInstallation(directory=None)
        self._active_worker: CallableWorker | None = None
        self._pending_query_record: SequenceRecord | None = None
        self._pending_query_fasta: Path | None = None
        self._pending_query_start0 = 0
        self._pending_query_end0 = 0
        self._last_blast_result: BlastSearchResult | None = None
        self._batch_blast_features: dict[str, Feature] = {}

        self._build_docks()
        self._build_central_tabs()
        self._build_menus()

        self.find_dialog = FindFeatureDialog(self.project_service, self)
        self.find_dialog.featureChosen.connect(self._on_find_feature_chosen)

        self._update_action_states()
        self.statusBar().showMessage("No project open")

        self.blast_panel.set_installation(self._blast_installation)

    # -- UI construction -----------------------------------------------------

    def _build_docks(self) -> None:
        self.explorer_dock = ProjectExplorerDock(self)
        self.explorer_dock.recordSelected.connect(self._on_record_selected)
        self.explorer_dock.topologyChangeRequested.connect(self._on_topology_change_requested)
        self.explorer_dock.deleteRecordRequested.connect(self._on_delete_record_requested)
        self.explorer_dock.moveRecordToFolderRequested.connect(
            self._on_move_record_to_folder_requested
        )
        self.explorer_dock.createFolderRequested.connect(self._on_create_folder_requested)
        self.explorer_dock.renameFolderRequested.connect(self._on_rename_folder_requested)
        self.explorer_dock.deleteFolderRequested.connect(self._on_delete_folder_requested)
        self.explorer_dock.moveFolderRequested.connect(self._on_move_folder_requested)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.explorer_dock)

        self.inspector_dock = InspectorDock(self)
        self.inspector_dock.featureUpdateRequested.connect(self._on_feature_update_requested)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.inspector_dock)

        self._log_view = QPlainTextEdit(self)
        self._log_view.setReadOnly(True)
        self._log_view.setMaximumBlockCount(2000)
        self.log_dock = QDockWidget("Jobs && Log", self)
        self.log_dock.setWidget(self._log_view)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.log_dock)

        self.blast_panel = BlastPanel(self)
        self.blast_panel.setupRequested.connect(self._on_blast_setup_requested)
        self.blast_panel.createDatabaseRequested.connect(self._on_create_database_requested)
        self.blast_panel.runRequested.connect(self._on_run_blast_requested)
        self.blast_panel.applyRequested.connect(self._on_apply_blast_hit_requested)
        self.blast_panel.cancelRequested.connect(self._on_cancel_blast_job)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.blast_panel)
        self.tabifyDockWidget(self.log_dock, self.blast_panel)
        self.blast_panel.raise_()

    def _build_central_tabs(self) -> None:
        self._tabs = QTabWidget(self)

        self.genome_map_page = GenomeMapPage(self)
        self.genome_map_page.featureClicked.connect(self._on_feature_selected_from_view)
        self.genome_map_page.featureDoubleClicked.connect(self._on_linear_feature_double_clicked)
        self.genome_map_page.selectionChanged.connect(self._on_canvas_selection_changed)
        self.genome_map_page.contextMenuRequestedAt.connect(self._on_canvas_context_menu)
        self.genome_map_page.featureBoundaryEditRequested.connect(
            self._on_feature_boundary_edit_requested
        )
        self._tabs.addTab(self.genome_map_page, "Genome Map")

        self.circular_canvas = CircularGenomeCanvas(self)
        self.circular_canvas.featureClicked.connect(self._on_feature_selected_from_view)
        self.circular_canvas.featureDoubleClicked.connect(self._on_circular_feature_double_clicked)
        self._tabs.addTab(self.circular_canvas, "Circular Map")

        self.feature_table = FeatureTableView(self)
        self.feature_table.featureSelected.connect(self._on_feature_selected_from_view)
        self.feature_table.batchEditQualifiersRequested.connect(
            self._on_batch_edit_qualifiers_requested
        )
        self.feature_table.applyTemplateRequested.connect(self._on_apply_template_requested)
        self.feature_table.batchBlastRequested.connect(self._on_batch_blast_requested)
        self._tabs.addTab(self.feature_table, "Feature Table")

        self.setCentralWidget(self._tabs)

    def _build_menus(self) -> None:
        file_menu = self.menuBar().addMenu("&File")
        self.action_new_project = make_action(self, "&New Project...", self._on_new_project)
        self.action_open_project = make_action(self, "&Open Project...", self._on_open_project)
        self.action_import_fasta = make_action(self, "Import &FASTA...", self._on_import_fasta)
        self.action_import_genbank = make_action(
            self, "Import &GenBank...", self._on_import_genbank
        )
        self.action_import_gff3 = make_action(self, "Import GFF&3...", self._on_import_gff3)
        self.action_save_project = make_action(
            self, "&Save Project", self._on_save_project, shortcut="Ctrl+S"
        )
        self.action_export_genbank = make_action(
            self, "&Export GenBank...", self._on_export_genbank
        )
        self.action_export_gff3 = make_action(self, "Export GFF&3...", self._on_export_gff3)
        self.action_export_nucleotide_fasta = make_action(
            self, "Export Nucleotide FASTA...", self._on_export_nucleotide_fasta
        )
        self.action_export_protein_fasta_records = make_action(
            self,
            "Export Protein FASTA (protein records)...",
            self._on_export_protein_fasta_records,
        )
        self.action_export_protein_fasta_cds = make_action(
            self,
            "Export Protein FASTA (CDS translations)...",
            self._on_export_protein_fasta_cds,
        )
        self.action_export_ffn = make_action(
            self, "Export FFN (CDS nucleotide)...", self._on_export_ffn
        )
        self.action_export_feature_csv = make_action(
            self, "Export Feature Table CSV...", self._on_export_feature_csv
        )
        self.action_exit = make_action(self, "E&xit", self._on_exit)
        for action in (
            self.action_new_project,
            self.action_open_project,
            None,
            self.action_import_fasta,
            self.action_import_genbank,
            self.action_import_gff3,
            None,
            self.action_save_project,
            self.action_export_genbank,
            self.action_export_gff3,
            self.action_export_nucleotide_fasta,
            self.action_export_protein_fasta_records,
            self.action_export_protein_fasta_cds,
            self.action_export_ffn,
            self.action_export_feature_csv,
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
        edit_menu.addSeparator()
        self.action_find_feature = make_action(
            self, "&Find Feature...", self._on_find_feature_requested, shortcut="Ctrl+F"
        )
        edit_menu.addAction(self.action_find_feature)

        annotation_menu = self.menuBar().addMenu("&Annotation")
        self.action_add_feature = make_action(self, "&Add Feature...", self._on_add_feature)
        annotation_menu.addAction(self.action_add_feature)

        view_menu = self.menuBar().addMenu("&View")
        self.action_zoom_whole_genome = make_action(
            self, "Fit &Whole Genome", lambda: self.genome_map_page.canvas.zoom_to_whole_genome()
        )
        self.action_zoom_selection = make_action(
            self, "Zoom to &Selection", lambda: self.genome_map_page.canvas.zoom_to_selection()
        )
        view_menu.addAction(self.action_zoom_whole_genome)
        view_menu.addAction(self.action_zoom_selection)

        blast_menu = self.menuBar().addMenu("&BLAST")
        self.action_blast_setup = make_action(
            self, "BLAST Setup...", self._on_blast_setup_requested
        )
        self.action_blast_create_db = make_action(
            self, "Create Database...", self._on_create_database_requested
        )
        blast_menu.addAction(self.action_blast_setup)
        blast_menu.addAction(self.action_blast_create_db)

        help_menu = self.menuBar().addMenu("&Help")
        help_menu.addAction(make_action(self, "&About", self._on_about))

    # -- Logging / state sync -------------------------------------------------

    def _log(self, message: str) -> None:
        logger.info(message)
        self._log_view.appendPlainText(message)

    def _update_action_states(self) -> None:
        is_open = self.project_service.is_open
        writable = is_open and not self.project_service.is_read_only
        has_record = self._current_record is not None
        has_records = is_open and bool(self.project_service.list_records())
        self.action_save_project.setEnabled(writable)
        self.action_export_genbank.setEnabled(has_records)
        self.action_export_gff3.setEnabled(has_records)
        self.action_export_nucleotide_fasta.setEnabled(has_records)
        self.action_export_protein_fasta_records.setEnabled(has_records)
        self.action_export_protein_fasta_cds.setEnabled(has_records)
        self.action_export_ffn.setEnabled(has_records)
        self.action_export_feature_csv.setEnabled(has_records)
        self.action_add_feature.setEnabled(has_record and writable)
        self.action_import_fasta.setEnabled(writable)
        self.action_import_genbank.setEnabled(writable)
        self.action_import_gff3.setEnabled(writable)
        self.action_undo.setEnabled(writable and self.project_service.undo_stack.can_undo)
        self.action_redo.setEnabled(writable and self.project_service.undo_stack.can_redo)
        self.action_find_feature.setEnabled(has_records)
        self.action_zoom_whole_genome.setEnabled(has_record)
        self.action_zoom_selection.setEnabled(has_record)
        if is_open and self.project_service.is_read_only:
            self.statusBar().showMessage("Project open read-only", 5000)

    def _refresh_project_explorer(self) -> None:
        if not self.project_service.is_open:
            self.explorer_dock.set_data([], [])
            return
        records = self.project_service.list_records()
        folders = self.project_service.list_folders()
        counts = {r.id: len(self.project_service.list_features(r.id)) for r in records}
        self.explorer_dock.set_data(records, folders, counts)

    def _refresh_current_record_views(self) -> None:
        features = (
            self.project_service.list_features(self._current_record.id)
            if self._current_record is not None
            else []
        )
        self.genome_map_page.set_record(self._current_record, features)
        self.circular_canvas.set_record(self._current_record, features)
        self.feature_table.set_features(features)
        if self._current_record is not None:
            self.inspector_dock.show_record(self._current_record)
            self.statusBar().showMessage(
                f"{self._current_record.display_id} — {self._current_record.length:,} bp"
            )
        else:
            self.inspector_dock.clear()
        self._apply_topology_tab_state()

    def _apply_topology_tab_state(self) -> None:
        """Circular Map only makes sense for a record actually assembled as circular.

        A linear molecule has no biological origin point to draw a ring around, so
        the tab is disabled (and the view falls back to the linear map) whenever the
        current record isn't circular, per the requirement that topology drives which
        map is shown.
        """
        circular_index = self._tabs.indexOf(self.circular_canvas)
        is_circular = (
            self._current_record is not None and self._current_record.topology == Topology.CIRCULAR
        )
        self._tabs.setTabEnabled(circular_index, is_circular)
        if not is_circular and self._tabs.currentIndex() == circular_index:
            self._tabs.setCurrentWidget(self.genome_map_page)

    def _select_default_tab_for_current_record(self) -> None:
        if self._current_record is not None and self._current_record.topology == Topology.CIRCULAR:
            self._tabs.setCurrentWidget(self.circular_canvas)
        else:
            self._tabs.setCurrentWidget(self.genome_map_page)

    def _refresh_features_only(self) -> None:
        if self._current_record is None:
            return
        features = self.project_service.list_features(self._current_record.id)
        self.genome_map_page.set_features(features)
        self.circular_canvas.set_features(features)
        self.feature_table.set_features(features)
        self._refresh_project_explorer()

    # -- File menu handlers --------------------------------------------------------

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
        except Exception as exc:  # noqa: BLE001
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
        self.open_project_at_path(path)

    def open_project_at_path(self, path: str) -> None:
        """Shared by the Open Project... dialog and startup (double-clicking
        a .gwbproj file, or the file-association command line %1)."""
        try:
            self.project_service.open(Path(path))
        except ProjectLockedError as exc:
            self._handle_locked_project(Path(path), exc)
            return
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Open Project Failed", str(exc))
            return
        self._current_record = None
        self._refresh_project_explorer()
        self._refresh_current_record_views()
        self._update_action_states()
        self._log(f"Opened project: {path}")

    def _handle_locked_project(self, path: Path, exc: ProjectLockedError) -> None:
        info = exc.lock_info
        choice = QMessageBox.warning(
            self,
            "Project Already Open",
            f"This project appears to already be open (pid={info.pid}, host={info.hostname}, "
            f"since {info.opened_at}), or it was not closed cleanly last time.\n\n"
            "Open read-only, or force-open for editing (only do this if you are sure no "
            "other instance has it open)?",
            buttons=QMessageBox.StandardButton.Open
            | QMessageBox.StandardButton.Retry
            | QMessageBox.StandardButton.Cancel,
        )
        # Open = read-only, Retry = force open for editing, Cancel = abort
        if choice == QMessageBox.StandardButton.Cancel:
            return
        try:
            if choice == QMessageBox.StandardButton.Open:
                self.project_service.open(path, read_only=True)
                self._log(f"Opened project read-only: {path}")
            else:
                self.project_service.open(path, force=True)
                self._log(f"Force-opened project for editing: {path}")
        except Exception as exc2:  # noqa: BLE001
            QMessageBox.critical(self, "Open Project Failed", str(exc2))
            return
        self._current_record = None
        self._refresh_project_explorer()
        self._refresh_current_record_views()
        self._update_action_states()

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
        if result.records:
            self._on_record_selected(result.records[0].id)

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
        if result.records:
            self._on_record_selected(result.records[0].id)

    def _on_import_gff3(self) -> None:
        if not self._guard_project_open():
            return
        path, _ = QFileDialog.getOpenFileName(self, "Import GFF3", "", "GFF3 (*.gff *.gff3 *.gz)")
        if not path:
            return
        result = self.import_service.import_gff3(Path(path))
        missing_sequence = any(not record.sequence for record in result.records)
        if missing_sequence:
            answer = QMessageBox.question(
                self,
                "GFF3 has no embedded sequence",
                "This GFF3 has no ##FASTA section, so records have no sequence yet. "
                "Select a matching FASTA file to pair with it now?",
            )
            if answer == QMessageBox.StandardButton.Yes:
                fasta_path, _ = QFileDialog.getOpenFileName(
                    self, "Matching FASTA", "", "FASTA (*.fasta *.fa *.fna *.fsa *.gz)"
                )
                if fasta_path:
                    for record in result.records:
                        self.project_service.get_repository().delete_record(record.id)
                    result = self.import_service.import_gff3(
                        Path(path), external_fasta_path=Path(fasta_path)
                    )
        self._refresh_project_explorer()
        self._update_action_states()
        self._log(f"Imported {len(result.records)} record(s) from {path}")
        for issue in result.issues:
            self._log(f"  [{issue.severity}] {issue.message}")
        if result.records:
            self._on_record_selected(result.records[0].id)

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

    def _on_export_gff3(self) -> None:
        if not self._guard_project_open():
            return
        records = self.project_service.list_records()
        if not records:
            QMessageBox.information(self, "Export GFF3", "No records to export.")
            return
        embed = QMessageBox.question(
            self, "Export GFF3", "Embed sequence as a ##FASTA section in the same file?"
        )
        path, _ = QFileDialog.getSaveFileName(self, "Export GFF3", "", "GFF3 (*.gff3)")
        if not path:
            return
        features_by_record_id = {
            record.id: self.project_service.list_features(record.id) for record in records
        }
        try:
            result = self.export_service.export_gff3(
                records,
                features_by_record_id,
                Path(path),
                embed_fasta=(embed == QMessageBox.StandardButton.Yes),
            )
        except ExportValidationError as exc:
            QMessageBox.critical(self, "Export Failed Validation", str(exc))
            return
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Export Failed", str(exc))
            return
        self._log(f"Exported {len(records)} record(s) to {result.destination}")
        for warning in result.warnings:
            self._log(f"  [warning] {warning.message}")

    def _on_export_nucleotide_fasta(self) -> None:
        self._export_one_way(
            "Export Nucleotide FASTA",
            "FASTA (*.fasta)",
            lambda records, features, dest: self.export_service.export_nucleotide_fasta(
                records, dest
            ),
        )

    def _on_export_protein_fasta_records(self) -> None:
        self._export_one_way(
            "Export Protein FASTA (protein records)",
            "FASTA (*.faa)",
            lambda records, features, dest: self.export_service.export_protein_fasta_from_records(
                records, dest
            ),
        )

    def _on_export_protein_fasta_cds(self) -> None:
        self._export_one_way(
            "Export Protein FASTA (CDS translations)",
            "FASTA (*.faa)",
            lambda records, features, dest: self.export_service.export_protein_fasta_from_cds(
                records, features, dest
            ),
        )

    def _on_export_ffn(self) -> None:
        self._export_one_way(
            "Export FFN",
            "FFN (*.ffn)",
            lambda records, features, dest: self.export_service.export_ffn(records, features, dest),
        )

    def _on_export_feature_csv(self) -> None:
        self._export_one_way(
            "Export Feature Table CSV",
            "CSV (*.csv)",
            lambda records, features, dest: self.export_service.export_feature_table_csv(
                records, features, dest
            ),
        )

    def _export_one_way(self, title: str, file_filter: str, run) -> None:
        if not self._guard_project_open():
            return
        records = self.project_service.list_records()
        if not records:
            QMessageBox.information(self, title, "No records to export.")
            return
        path, _ = QFileDialog.getSaveFileName(self, title, "", file_filter)
        if not path:
            return
        features_by_record_id = {
            record.id: self.project_service.list_features(record.id) for record in records
        }
        try:
            destination, count = run(records, features_by_record_id, Path(path))
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, f"{title} Failed", str(exc))
            return
        self._log(f"{title}: wrote {count} record(s)/row(s) to {destination}")

    def _refresh_current_record_after_undo_redo(self) -> None:
        # Re-fetch rather than just re-listing features: some commands (e.g.
        # RecordTopologyChangeCommand) mutate the record itself, not just its
        # features, and _refresh_current_record_views() reads from the cached
        # self._current_record.
        if self._current_record is not None:
            self._current_record = self.project_service.get_record(self._current_record.id)
        self._refresh_current_record_views()

    def _on_undo(self) -> None:
        if self.project_service.undo_stack.undo():
            self._refresh_current_record_after_undo_redo()
            self._update_action_states()
            self._log("Undo")

    def _on_redo(self) -> None:
        if self.project_service.undo_stack.redo():
            self._refresh_current_record_after_undo_redo()
            self._update_action_states()
            self._log("Redo")

    def _on_add_feature(self) -> None:
        if self._current_record is None:
            return
        selection = self.genome_map_page.canvas.current_selection()
        initial_start = selection[0] + 1 if selection else None
        initial_end = selection[1] if selection else None
        dialog = AddFeatureDialog(
            self._current_record,
            self.annotation_service,
            self,
            initial_start_1based=initial_start,
            initial_end_1based=initial_end,
            templates_dir=self._templates_dir,
        )
        if dialog.exec():
            self._refresh_features_only()
            self._update_action_states()
            if dialog.created_feature is not None:
                self._log(f"Created feature: {dialog.created_feature.computed_label()}")

    def _on_about(self) -> None:
        QMessageBox.about(
            self,
            f"About {APP_NAME}",
            f"{APP_NAME} {APP_VERSION}\nLocal genome sequence visualization "
            "and annotation workbench.",
        )

    def _on_exit(self) -> None:
        self.close()

    def _on_topology_change_requested(self, record_id: str, topology_value: str) -> None:
        if not self._guard_project_open():
            return
        record = self.project_service.set_record_topology(record_id, Topology(topology_value))
        self._refresh_project_explorer()
        if self._current_record is not None and self._current_record.id == record_id:
            self._current_record = record
            self._refresh_current_record_views()
            self._select_default_tab_for_current_record()
        self._update_action_states()
        self._log(f"Set {record.display_id} topology to {topology_value}")

    def _on_delete_record_requested(self, record_id: str) -> None:
        if not self._guard_project_open():
            return
        record = self.project_service.get_record(record_id)
        display_id = record.display_id if record is not None else record_id
        self.project_service.delete_record(record_id)
        if self._current_record is not None and self._current_record.id == record_id:
            self._current_record = None
            self._current_feature = None
            self._refresh_current_record_views()
        self._refresh_project_explorer()
        self._update_action_states()
        self._log(f"Deleted record: {display_id}")

    def _on_move_record_to_folder_requested(self, record_id: str, folder_id: str) -> None:
        if not self._guard_project_open():
            return
        self.project_service.move_record_to_folder(record_id, folder_id or None)
        self._refresh_project_explorer()

    def _on_create_folder_requested(self, name: str, parent_folder_id: str) -> None:
        if not self._guard_project_open():
            return
        self.project_service.create_folder(name, parent_folder_id or None)
        self._refresh_project_explorer()

    def _on_rename_folder_requested(self, folder_id: str, new_name: str) -> None:
        if not self._guard_project_open():
            return
        self.project_service.rename_folder(folder_id, new_name)
        self._refresh_project_explorer()

    def _on_delete_folder_requested(self, folder_id: str) -> None:
        if not self._guard_project_open():
            return
        self.project_service.delete_folder(folder_id)
        self._refresh_project_explorer()

    def _on_move_folder_requested(self, folder_id: str, new_parent_folder_id: str) -> None:
        if not self._guard_project_open():
            return
        try:
            self.project_service.move_folder(folder_id, new_parent_folder_id or None)
        except ValueError as exc:
            QMessageBox.warning(self, "Move to Folder", str(exc))
            return
        self._refresh_project_explorer()

    # -- Record / feature selection sync --------------------------------------

    def _on_record_selected(self, record_id: str) -> None:
        record = self.project_service.get_record(record_id)
        self._current_record = record
        self._current_feature = None
        self._refresh_current_record_views()
        self._update_action_states()
        self._select_default_tab_for_current_record()

    def _on_find_feature_requested(self) -> None:
        if not self._guard_project_open():
            return
        self.find_dialog.open_for_search()

    def _on_find_feature_chosen(self, record_id: str, feature_id: str) -> None:
        if self._current_record is None or self._current_record.id != record_id:
            self._on_record_selected(record_id)
        self._tabs.setCurrentWidget(self.genome_map_page)
        self.genome_map_page.zoom_to_feature(feature_id)
        self._on_feature_selected_from_view(feature_id)

    def _find_current_feature(self, feature_id: str) -> Feature | None:
        if self._current_record is None:
            return None
        for feature in self.project_service.list_features(self._current_record.id):
            if feature.id == feature_id:
                return feature
        return None

    def _on_feature_selected_from_view(self, feature_id: str) -> None:
        feature = self._find_current_feature(feature_id)
        if feature is None or self._current_record is None:
            return
        self._current_feature = feature
        self.inspector_dock.show_feature(feature, self._current_record)
        self.genome_map_page.select_feature(feature_id)
        self.circular_canvas.select_feature(feature_id)
        self.feature_table.select_feature_row(feature_id)

    def _on_linear_feature_double_clicked(self, feature_id: str) -> None:
        self._tabs.setCurrentWidget(self.genome_map_page)
        self.genome_map_page.zoom_to_feature(feature_id)
        self._on_feature_selected_from_view(feature_id)

    def _on_circular_feature_double_clicked(self, feature_id: str) -> None:
        self._tabs.setCurrentWidget(self.genome_map_page)
        self.genome_map_page.zoom_to_feature(feature_id)
        self._on_feature_selected_from_view(feature_id)

    def _on_feature_update_requested(self, before: Feature, after: Feature) -> None:
        self.annotation_service.update_feature(before, after)
        self._refresh_features_only()
        if self._current_record is not None:
            self.inspector_dock.show_feature(after, self._current_record)
        self._log(f"Updated feature: {after.computed_label()}")

    def _on_batch_edit_qualifiers_requested(self, feature_ids: list) -> None:
        if not self._guard_project_open():
            return
        features = [f for f in (self._find_current_feature(fid) for fid in feature_ids) if f]
        if not features:
            return
        dialog = BatchQualifierDialog(len(features), self)
        if not dialog.exec():
            return
        key = dialog.key()
        if not key:
            return
        updated = self.annotation_service.batch_update_qualifier(
            features, dialog.operation(), key, dialog.value()
        )
        self._refresh_features_only()
        self._log(f"Batch {dialog.operation()} qualifier '{key}' on {len(updated)} feature(s)")

    def _on_apply_template_requested(self, feature_ids: list) -> None:
        if not self._guard_project_open():
            return
        features = [f for f in (self._find_current_feature(fid) for fid in feature_ids) if f]
        if not features:
            return
        templates = load_templates(self._templates_dir)
        if not templates:
            QMessageBox.information(
                self,
                "Apply Template",
                "No saved templates yet -- save one from the Add Feature dialog first.",
            )
            return
        name, ok = QInputDialog.getItem(
            self, "Apply Template", "Template:", [t.name for t in templates], editable=False
        )
        if not ok:
            return
        template = next(t for t in templates if t.name == name)
        updated = self.annotation_service.apply_template_to_features(features, template)
        self._refresh_features_only()
        self._log(f"Applied template '{template.name}' to {len(updated)} feature(s)")

    def _on_feature_boundary_edit_requested(
        self, feature_id: str, new_start0: int, new_end0: int
    ) -> None:
        before = self._find_current_feature(feature_id)
        if before is None:
            return
        if len(before.parts) != 1:
            QMessageBox.information(
                self,
                "Cannot Resize",
                "Boundary dragging is only supported for simple (single-part) features.",
            )
            return
        after = Feature(
            id=before.id,
            record_id=before.record_id,
            type=before.type,
            strand=before.strand,
            location_operator=before.location_operator,
            parts=[LocationPart(start0=new_start0, end0=new_end0, order_index=0)],
            qualifiers=before.qualifiers,
            display_label=before.display_label,
            parent_ids=list(before.parent_ids),
            child_ids=list(before.child_ids),
            source=before.source,
            score=before.score,
            phase=before.phase,
            provenance_id=before.provenance_id,
            created_at=before.created_at,
            revision=before.revision,
        )
        self._on_feature_update_requested(before, after)

    # -- Selection / context menu ---------------------------------------------------

    def _on_canvas_selection_changed(self, start0: int, end0: int) -> None:
        if start0 < 0:
            self.statusBar().showMessage(
                f"{self._current_record.display_id}" if self._current_record else ""
            )
            return
        length = end0 - start0
        record_label = self._current_record.display_id if self._current_record else ""
        self.statusBar().showMessage(
            f"{record_label}  selection {start0 + 1:,}..{end0:,} ({length:,} bp)"
        )

    # Menu construction (real modal popup) is kept separate from action
    # dispatch (_dispatch_selection_action) so tests can drive the dispatch
    # logic directly instead of fighting QMenu.exec()'s blocking nested
    # event loop (a PySide6/Shiboken-bound method that cannot be
    # monkeypatched from Python — assigning QMenu.exec silently has no
    # effect and the real modal call hangs forever under a fake click).
    def _on_canvas_context_menu(self, global_pos: QPoint, start0: int, end0: int) -> None:
        if self._current_record is None:
            return
        menu = QMenu(self)
        actions = {
            "add_annotation": menu.addAction("Add Annotation..."),
            "run_blast": menu.addAction("Run BLAST..."),
        }
        menu.addSeparator()
        actions["copy"] = menu.addAction("Copy Sequence")
        actions["copy_rc"] = menu.addAction("Copy Reverse Complement")
        actions["translate_plus"] = menu.addAction("Translate (+ strand)")
        actions["translate_minus"] = menu.addAction("Translate (- strand)")
        menu.addSeparator()
        actions["export"] = menu.addAction("Export Selection as FASTA...")
        actions["extract_record"] = menu.addAction("Extract Selection as New Record...")
        actions["reverse_complement_record"] = menu.addAction(
            "Reverse Complement Whole Record as New Record..."
        )

        chosen = menu.exec(global_pos)
        if chosen is None:
            return
        key = next((k for k, action in actions.items() if action is chosen), None)
        if key is not None:
            self._dispatch_selection_action(key, start0, end0)

    def _dispatch_selection_action(self, key: str, start0: int, end0: int) -> None:
        record = self._current_record
        if record is None:
            return
        if key == "add_annotation":
            dialog = AddFeatureDialog(
                record,
                self.annotation_service,
                self,
                initial_start_1based=start0 + 1,
                initial_end_1based=end0,
                templates_dir=self._templates_dir,
            )
            if dialog.exec():
                self._refresh_features_only()
                self._update_action_states()
        elif key == "run_blast":
            self._start_blast_from_selection(record, start0, end0)
        elif key == "copy":
            QApplication.clipboard().setText(
                self.sequence_ops_service.get_selection(record, start0, end0)
            )
        elif key == "copy_rc":
            QApplication.clipboard().setText(
                self.sequence_ops_service.get_selection_reverse_complement(record, start0, end0)
            )
        elif key == "translate_plus":
            protein = self.sequence_ops_service.get_selection_translation(
                record, start0, end0, strand=1
            )
            QMessageBox.information(self, "Translation (+ strand)", protein or "(empty)")
        elif key == "translate_minus":
            protein = self.sequence_ops_service.get_selection_translation(
                record, start0, end0, strand=-1
            )
            QMessageBox.information(self, "Translation (- strand)", protein or "(empty)")
        elif key == "export":
            path, _ = QFileDialog.getSaveFileName(self, "Export Selection", "", "FASTA (*.fasta)")
            if path:
                self.sequence_ops_service.export_selection_fasta(record, start0, end0, Path(path))
                self._log(f"Exported selection {start0 + 1}..{end0} to {path}")
        elif key == "extract_record":
            self._extract_selection_as_new_record(record, start0, end0)
        elif key == "reverse_complement_record":
            self._reverse_complement_record_as_new(record)

    def _extract_selection_as_new_record(
        self, record: SequenceRecord, start0: int, end0: int
    ) -> None:
        if not self._guard_project_open():
            return
        new_record = self.sequence_ops_service.extract_as_new_record(record, start0, end0)
        repo = self.project_service.require_writable()
        repo.save_record(new_record)
        self.project_service.log_audit(
            EventType.SEQUENCE_OPERATION,
            new_record.id,
            f"Extracted new record '{new_record.display_id}' from {record.display_id}:"
            f"{start0 + 1}..{end0}",
        )
        self.project_service.touch()
        self._refresh_project_explorer()
        self._log(f"Created new record: {new_record.display_id} ({new_record.length} bp)")

    def _reverse_complement_record_as_new(self, record: SequenceRecord) -> None:
        if not self._guard_project_open():
            return
        new_record = self.sequence_ops_service.reverse_complement_as_new_record(record)
        repo = self.project_service.require_writable()
        repo.save_record(new_record)
        self.project_service.log_audit(
            EventType.SEQUENCE_OPERATION,
            new_record.id,
            f"Created reverse-complement record '{new_record.display_id}' from {record.display_id}",
        )
        self.project_service.touch()
        self._refresh_project_explorer()
        self._log(f"Created new record: {new_record.display_id} ({new_record.length} bp)")

    def _guard_project_open(self) -> bool:
        if not self.project_service.is_open:
            QMessageBox.warning(self, "No Project Open", "Open or create a project first.")
            return False
        return True

    # -- BLAST -----------------------------------------------------------------------

    def _on_blast_setup_requested(self) -> None:
        dialog = BlastSetupDialog(self._blast_installation.directory, self)
        dialog.exec()
        self._blast_installation = dialog.installation
        self.blast_panel.set_installation(self._blast_installation)
        self._log(
            "BLAST installation "
            + (
                "fully detected."
                if self._blast_installation.is_fully_installed()
                else "incomplete."
            )
        )

    def _on_create_database_requested(self) -> None:
        if self._active_worker is not None:
            QMessageBox.information(
                self, "Create Database", "A BLAST job is already running. Cancel it first."
            )
            return
        if not self._blast_installation.has("makeblastdb") or not self._blast_installation.has(
            "blastdbcmd"
        ):
            QMessageBox.warning(
                self,
                "BLAST Not Configured",
                "makeblastdb/blastdbcmd were not found. Run BLAST Setup first.",
            )
            return
        dialog = CreateBlastDatabaseDialog(self)
        if not dialog.exec():
            return
        source_fasta = dialog.source_fasta()
        molecule_type = dialog.molecule_type()
        name = dialog.database_name()
        if not source_fasta.exists():
            QMessageBox.warning(self, "Create Database", f"File not found: {source_fasta}")
            return

        self._log(f"Building BLAST database '{name}' from {source_fasta} ...")
        worker = CallableWorker(
            self.blast_service.create_database,
            self._blast_installation,
            source_fasta,
            molecule_type,
            name,
        ).with_cancel_support()
        worker.succeeded.connect(self._on_database_created)
        worker.failed.connect(lambda msg: self._on_blast_job_failed("Database Creation", msg))
        self._active_worker = worker
        self.blast_panel.set_job_running(True, f"Building database '{name}'...")
        worker.start()

    def _on_database_created(self, database) -> None:
        self.blast_panel.set_databases(self.blast_service.list_databases())
        self._log(f"Created BLAST database '{database.name}' ({database.sequence_count} sequences)")
        self._active_worker = None
        self.blast_panel.set_job_running(False)

    def _start_blast_from_selection(self, record: SequenceRecord, start0: int, end0: int) -> None:
        if not self.blast_service.list_databases():
            QMessageBox.information(
                self,
                "Run BLAST",
                "No BLAST database registered yet. Use BLAST > Create Database... first.",
            )
            return
        jobs_dir = self.blast_service.work_dir / "jobs"
        jobs_dir.mkdir(parents=True, exist_ok=True)
        query_fasta = jobs_dir / f"query_{record.id}_{start0}_{end0}.fasta"
        sequence = self.sequence_ops_service.get_selection(record, start0, end0)
        query_fasta.write_text(
            f">{record.display_id}:{start0 + 1}-{end0}\n{sequence}\n", encoding="utf-8"
        )

        self._pending_query_record = record
        self._pending_query_fasta = query_fasta
        self._pending_query_start0 = start0
        self._pending_query_end0 = end0

        self.blast_panel.set_query_context(
            f"Selection: {record.display_id}:{start0 + 1}-{end0} ({end0 - start0} bp, + strand)"
        )
        selected_db = self.blast_panel.selected_database()
        if selected_db is not None:
            self.blast_panel.set_suggested_program(
                suggest_program(record.molecule_type, selected_db.molecule_type)
            )
        self.blast_panel.set_databases(self.blast_service.list_databases())
        self.blast_panel.raise_()

    def _on_run_blast_requested(self) -> None:
        if self._active_worker is not None:
            QMessageBox.information(
                self, "Run BLAST", "A BLAST job is already running. Cancel it first."
            )
            return
        if self._pending_query_fasta is None or self._pending_query_record is None:
            QMessageBox.information(
                self,
                "Run BLAST",
                "Select a region on the Genome Map and choose 'Run BLAST...' first.",
            )
            return
        database = self.blast_panel.selected_database()
        if database is None:
            QMessageBox.information(self, "Run BLAST", "Select a database first.")
            return
        program = self.blast_panel.selected_program()
        if not self._blast_installation.has(program.value):
            QMessageBox.warning(
                self, "Run BLAST", f"{program.value} is not available. Run BLAST Setup first."
            )
            return
        params = self.blast_panel.search_parameters()

        self._log(f"Running {program.value} against '{database.name}' ...")
        worker = CallableWorker(
            self.blast_service.run_search,
            self._blast_installation,
            database,
            program,
            self._pending_query_fasta,
            params,
            self._pending_query_record.id,
            self._pending_query_start0,
            self._pending_query_end0,
            1,
        ).with_cancel_support()
        worker.succeeded.connect(self._on_blast_search_finished)
        worker.failed.connect(lambda msg: self._on_blast_job_failed("BLAST Search", msg))
        self._active_worker = worker
        self.blast_panel.set_job_running(
            True, f"Running {program.value} against '{database.name}'..."
        )
        worker.start()

    def _on_blast_search_finished(self, result: BlastSearchResult) -> None:
        self._last_blast_result = result
        self.blast_panel.set_result(result)
        self._log(f"BLAST search complete: {len(result.hits)} hit(s)")
        self._active_worker = None
        self.blast_panel.set_job_running(False)

    def _on_batch_blast_requested(self, feature_ids: list) -> None:
        if not self._guard_project_open():
            return
        if self._active_worker is not None:
            QMessageBox.information(
                self, "Batch BLAST", "A BLAST job is already running. Cancel it first."
            )
            return
        if self._current_record is None:
            return
        features = [f for f in (self._find_current_feature(fid) for fid in feature_ids) if f]
        if len(features) < 2:
            return
        if not self.blast_service.list_databases():
            QMessageBox.information(
                self,
                "Batch BLAST",
                "No BLAST database registered yet. Use BLAST > Create Database... first.",
            )
            return
        database = self.blast_panel.selected_database()
        if database is None:
            QMessageBox.information(self, "Batch BLAST", "Select a database first.")
            return
        program = self.blast_panel.selected_program()
        if not self._blast_installation.has(program.value):
            QMessageBox.warning(
                self,
                "Batch BLAST",
                f"{program.value} is not available. Run BLAST Setup first.",
            )
            return
        params = self.blast_panel.search_parameters()

        record = self._current_record
        jobs_dir = self.blast_service.work_dir / "jobs"
        jobs_dir.mkdir(parents=True, exist_ok=True)
        queries = []
        for feature in features:
            sequence = extract_sequence(
                record.sequence, feature.parts, feature.strand, record.length
            )
            query_fasta = jobs_dir / f"batch_query_{feature.id}.fasta"
            query_fasta.write_text(f">{feature.computed_label()}\n{sequence}\n", encoding="utf-8")
            queries.append(
                (
                    feature.id,
                    query_fasta,
                    record.id,
                    feature.start0,
                    feature.end0,
                    feature.strand or 1,
                )
            )

        self._batch_blast_features = {f.id: f for f in features}
        self._log(
            f"Running batch {program.value} against '{database.name}' "
            f"for {len(queries)} feature(s)..."
        )
        worker = CallableWorker(
            self.blast_service.run_batch_search,
            self._blast_installation,
            database,
            program,
            queries,
            params,
        ).with_cancel_support()
        worker.succeeded.connect(self._on_batch_blast_finished)
        worker.failed.connect(lambda msg: self._on_blast_job_failed("Batch BLAST", msg))
        self._active_worker = worker
        self.blast_panel.set_job_running(
            True, f"Batch {program.value} on {len(queries)} feature(s)..."
        )
        worker.start()

    def _on_batch_blast_finished(self, results: list) -> None:
        self._active_worker = None
        self.blast_panel.set_job_running(False)
        self._log(f"Batch BLAST complete: {len(results)} feature(s) processed")
        if self._current_record is None:
            return
        dialog = BatchBlastResultsDialog(
            results,
            self._batch_blast_features,
            self._current_record,
            self.blast_service,
            self.annotation_service,
            self,
        )
        dialog.exec()
        if dialog.applied_feature_ids:
            self._refresh_features_only()
            self._log(f"Applied {len(dialog.applied_feature_ids)} hit(s) from batch BLAST")

    def _on_cancel_blast_job(self) -> None:
        if self._active_worker is not None:
            self._active_worker.cancel()
            self._log("Cancelling BLAST job...")

    def _on_blast_job_failed(self, title: str, message: str) -> None:
        self._active_worker = None
        self.blast_panel.set_job_running(False)
        if "cancelled by the user" in message:
            self._log(f"{title} cancelled by the user.")
            return
        QMessageBox.critical(self, f"{title} Failed", message)

    def _on_apply_blast_hit_requested(self) -> None:
        if self._last_blast_result is None or self._pending_query_record is None:
            return
        hit = self.blast_panel.selected_hit()
        if hit is None or not hit.hsps:
            QMessageBox.information(self, "Apply Hit", "Select a hit first.")
            return
        hsp = hit.hsps[0]
        dialog = ApplyBlastHitDialog(
            self._pending_query_record, self._last_blast_result, hit, hsp, self
        )
        if not dialog.exec():
            return
        genome_start0, genome_end0, genome_strand = dialog.mapped_location()
        feature = self.blast_service.apply_hit_as_annotation(
            self.annotation_service,
            self._pending_query_record,
            self._last_blast_result,
            hit,
            hsp,
            dialog.feature_type(),
            dialog.build_qualifiers(),
        )
        if (
            self._current_record is not None
            and self._current_record.id == self._pending_query_record.id
        ):
            self._refresh_features_only()
        self._log(
            f"Applied BLAST hit as {feature.type} feature at "
            f"{genome_start0 + 1}..{genome_end0} (strand {genome_strand:+d})"
        )

    # -- Qt overrides ------------------------------------------------------------------

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt override signature
        self.project_service.close()
        super().closeEvent(event)
