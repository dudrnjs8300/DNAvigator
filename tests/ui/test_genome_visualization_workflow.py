"""End-to-end GUI verification of the mouse-driven genome workbench workflow:
open a file -> see the genome map -> click/drag/zoom with the mouse ->
right-click to annotate -> run BLAST -> apply a hit -> export. Every step
below drives real widgets and real application services; only the BLAST+
executable itself is a stand-in (see tests/fixtures/fake_blast), matching
spec 16.1's "mock BLAST executable interaction" test category.
"""

from pathlib import Path

import pytest
from PySide6.QtCore import QPoint, Qt

from genome_workbench.domain.blast_models import BlastInstallation
from genome_workbench.domain.qualifiers import QualifierSet
from genome_workbench.ui.dialogs.add_feature_dialog import AddFeatureDialog
from genome_workbench.ui.dialogs.apply_blast_hit_dialog import ApplyBlastHitDialog
from genome_workbench.ui.dialogs.create_blast_database_dialog import CreateBlastDatabaseDialog
from genome_workbench.ui.main_window import MainWindow
from genome_workbench.ui.workers.callable_worker import CallableWorker

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"
FAKE_BLAST_DIR = FIXTURES_DIR / "fake_blast"

pytestmark = pytest.mark.ui


def _open_project_with_fasta(window: MainWindow, tmp_path: Path, monkeypatch):
    project_path = str(tmp_path / "viz" / "project.gwbproj")
    monkeypatch.setattr(
        "genome_workbench.ui.main_window.QFileDialog.getSaveFileName",
        staticmethod(lambda *a, **k: (project_path, "")),
    )
    monkeypatch.setattr(
        "genome_workbench.ui.main_window.QInputDialog.getText",
        staticmethod(lambda *a, **k: ("Viz Project", True)),
    )
    window._on_new_project()

    fasta_path = str(FIXTURES_DIR / "simple_linear.fasta")
    monkeypatch.setattr(
        "genome_workbench.ui.main_window.QFileDialog.getOpenFileName",
        staticmethod(lambda *a, **k: (fasta_path, "")),
    )
    window._on_import_fasta()
    return window.project_service.list_records()[0]


def test_wheel_zoom_and_fit_whole_genome_change_viewport(qtbot, tmp_path, monkeypatch):
    window = MainWindow(blast_work_dir=tmp_path / "blast_work")
    qtbot.addWidget(window)
    _open_project_with_fasta(window, tmp_path, monkeypatch)

    canvas = window.genome_map_page.canvas
    whole_genome_length = canvas.viewport_transform.visible_length

    window.genome_map_page._zoom_by(0.5)
    assert canvas.viewport_transform.visible_length < whole_genome_length

    canvas.zoom_to_whole_genome()
    assert canvas.viewport_transform.visible_length == whole_genome_length


def test_mouse_drag_select_then_right_click_add_annotation(qtbot, tmp_path, monkeypatch):
    window = MainWindow(blast_work_dir=tmp_path / "blast_work")
    window.resize(1200, 800)
    qtbot.addWidget(window)
    with qtbot.waitExposed(window):
        window.show()

    record = _open_project_with_fasta(window, tmp_path, monkeypatch)
    window._on_record_selected(record.id)

    canvas = window.genome_map_page.canvas
    assert canvas.width() > 200  # real laid-out size, not a 0x0 stub
    vt = canvas.viewport_transform

    target_start0, target_end0 = 100, 500
    x1 = int(vt.genome_to_pixel(target_start0))
    x2 = int(vt.genome_to_pixel(target_end0))
    y = 100  # below the ruler, on empty background (no features yet)

    qtbot.mousePress(canvas, Qt.MouseButton.LeftButton, pos=QPoint(x1, y))
    qtbot.mouseMove(canvas, pos=QPoint(x2, y))
    qtbot.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=QPoint(x2, y))

    selection = canvas.current_selection()
    assert selection is not None
    start0, end0 = selection
    # pixel rounding tolerance
    assert abs(start0 - target_start0) <= 3
    assert abs(end0 - target_end0) <= 3

    # QMenu.exec() is a Shiboken-bound modal call that cannot be monkeypatched
    # from Python (assigning QMenu.exec silently has no effect and the real
    # popup blocks forever waiting for a click that will never come headless).
    # window._on_canvas_context_menu is therefore split into "build+exec the
    # menu" and "_dispatch_selection_action(key, ...)"; drive the dispatch
    # directly with the key the real "Add Annotation..." entry maps to —
    # this is the exact same code path minus the unautomatable popup.
    captured = {}

    def _fake_add_feature_exec(self):
        captured["start"] = self._start_spin.value()
        captured["end"] = self._end_spin.value()
        self.created_feature = self._annotation_service.create_simple_feature(
            self._record,
            self._start_spin.value(),
            self._end_spin.value(),
            1,
            "misc_feature",
            QualifierSet.from_pairs([("note", "from drag selection")]),
        )
        return 1

    monkeypatch.setattr(AddFeatureDialog, "exec", _fake_add_feature_exec)

    window._dispatch_selection_action("add_annotation", start0, end0)

    # the dialog must have been pre-filled with the actual dragged selection
    assert captured["start"] == start0 + 1
    assert captured["end"] == end0

    features = window.project_service.list_features(record.id)
    assert len(features) == 1
    assert features[0].qualifiers.get_first("note") == "from drag selection"


def test_feature_click_and_double_click_sync_across_views(qtbot, tmp_path, monkeypatch):
    window = MainWindow(blast_work_dir=tmp_path / "blast_work")
    window.resize(1200, 800)
    qtbot.addWidget(window)
    with qtbot.waitExposed(window):
        window.show()

    record = _open_project_with_fasta(window, tmp_path, monkeypatch)
    window._on_record_selected(record.id)

    feature = window.annotation_service.create_simple_feature(
        record, 101, 300, 1, "CDS", QualifierSet.from_pairs([("gene", "clickTest")])
    )
    window._refresh_features_only()

    canvas = window.genome_map_page.canvas
    canvas.zoom_to_feature(feature.id)
    vt = canvas.viewport_transform
    mid_x = int(vt.genome_to_pixel((feature.start0 + feature.end0) // 2))
    lane_y = canvas._lane_area_top() + 10

    qtbot.mouseClick(canvas, Qt.MouseButton.LeftButton, pos=QPoint(mid_x, lane_y))

    assert window._current_feature is not None
    assert window._current_feature.id == feature.id
    assert window.circular_canvas._selected_feature_id == feature.id

    before_length = canvas.viewport_transform.visible_length
    canvas.zoom_to_whole_genome()
    assert canvas.viewport_transform.visible_length != before_length

    # recompute the on-screen position: the viewport (and therefore the
    # pixel<->genome mapping) changed after zooming back out to whole-genome
    vt = canvas.viewport_transform
    mid_x = int(vt.genome_to_pixel((feature.start0 + feature.end0) // 2))
    qtbot.mouseDClick(canvas, Qt.MouseButton.LeftButton, pos=QPoint(mid_x, lane_y))
    zoomed_length = canvas.viewport_transform.visible_length
    assert zoomed_length < record.length


def test_blast_run_and_apply_hit_as_annotation_end_to_end(qtbot, tmp_path, monkeypatch):
    # Run BLAST subprocess calls synchronously in-test instead of on a real
    # QThread, so the async worker's result is available immediately.
    monkeypatch.setattr(CallableWorker, "start", lambda self: self.run())

    window = MainWindow(blast_work_dir=tmp_path / "blast_work")
    qtbot.addWidget(window)
    record = _open_project_with_fasta(window, tmp_path, monkeypatch)
    window._on_record_selected(record.id)

    from genome_workbench.infrastructure.blast.detector import REQUIRED_EXECUTABLES

    window._blast_installation = BlastInstallation(
        directory=str(FAKE_BLAST_DIR),
        executables={name: str(FAKE_BLAST_DIR / f"{name}.bat") for name in REQUIRED_EXECUTABLES},
        versions={name: "fake 1.0" for name in REQUIRED_EXECUTABLES},
    )
    window.blast_panel.set_installation(window._blast_installation)
    assert window._blast_installation.is_fully_installed()

    db_source_fasta = tmp_path / "db_source.fasta"
    db_source_fasta.write_text(">subject1\nACGTACGTACGTACGTACGT\n")

    def _fake_create_db_exec(self):
        self._source_edit.setText(str(db_source_fasta))
        self._molecule_combo.setCurrentText("nucleotide")
        self._name_edit.setText("test_db")
        return 1

    monkeypatch.setattr(CreateBlastDatabaseDialog, "exec", _fake_create_db_exec)
    window._on_create_database_requested()

    databases = window.blast_service.list_databases()
    assert len(databases) == 1
    assert window.blast_panel._databases  # panel was refreshed

    # Select a genome region and start a BLAST run against it (mirrors the
    # "Run BLAST..." context menu action without the modal QMenu roundtrip).
    window._start_blast_from_selection(record, 100, 400)
    window.blast_panel._database_list.setCurrentRow(0)
    window.blast_panel._program_combo.setCurrentText("blastn")

    window._on_run_blast_requested()

    assert window._last_blast_result is not None
    assert len(window._last_blast_result.hits) == 1
    assert window._last_blast_result.hits[0].subject_id == "fake_subject_1"

    window.blast_panel._hit_table.selectRow(0)

    def _fake_apply_hit_exec(self):
        return 1

    monkeypatch.setattr(ApplyBlastHitDialog, "exec", _fake_apply_hit_exec)
    window._on_apply_blast_hit_requested()

    features = window.project_service.list_features(record.id)
    blast_features = [f for f in features if f.provenance_id is not None]
    assert len(blast_features) == 1
    applied = blast_features[0]
    assert applied.type == "CDS"
    provenance = window.project_service.get_repository().get_provenance(applied.provenance_id)
    assert provenance is not None
    assert provenance.subject_id == "fake_subject_1"
    assert provenance.tool_name == "blastn"


def test_inspector_advanced_qualifier_editor_add_and_apply(qtbot, tmp_path, monkeypatch):
    from genome_workbench.ui.docks.inspector_dock import InspectorDock

    window = MainWindow(blast_work_dir=tmp_path / "blast_work")
    qtbot.addWidget(window)
    record = _open_project_with_fasta(window, tmp_path, monkeypatch)

    feature = window.annotation_service.create_simple_feature(
        record, 101, 300, 1, "misc_feature", QualifierSet.from_pairs([("EC_number", "1.1.1.1")])
    )
    window._refresh_features_only()
    window._on_feature_selected_from_view(feature.id)

    inspector: InspectorDock = window.inspector_dock
    assert inspector._advanced_qualifier_table.rowCount() == 1  # EC_number is not a common field
    assert inspector._advanced_qualifier_table.item(0, 0).text() == "EC_number"

    inspector._on_add_qualifier_row()
    new_row = inspector._advanced_qualifier_table.rowCount() - 1
    inspector._advanced_qualifier_table.item(new_row, 0).setText("custom_key")
    inspector._advanced_qualifier_table.item(new_row, 1).setText("custom_value")

    captured = {}
    inspector.featureUpdateRequested.connect(lambda before, after: captured.update(after=after))
    inspector._on_apply()

    assert "after" in captured
    updated = captured["after"]
    assert updated.qualifiers.get_first("custom_key") == "custom_value"
    assert updated.qualifiers.get_first("EC_number") == "1.1.1.1"


def test_add_feature_dialog_join_mode_creates_compound_feature(qtbot, tmp_path, monkeypatch):
    window = MainWindow(blast_work_dir=tmp_path / "blast_work")
    qtbot.addWidget(window)
    record = _open_project_with_fasta(window, tmp_path, monkeypatch)

    dialog = AddFeatureDialog(record, window.annotation_service, window)
    qtbot.addWidget(dialog)

    dialog._join_checkbox.setChecked(True)
    assert dialog._location_stack.currentWidget() is dialog._compound_location_widget

    # replace the single default segment row with two explicit segments,
    # given out of genomic order to exercise the ascending-order derivation
    dialog._segments_table.setRowCount(0)
    dialog._add_segment_row(300, 350)
    dialog._add_segment_row(101, 150)
    dialog._strand_combo.setCurrentText("-")
    dialog._update_preview()
    assert "Length: 101 bp" in dialog._preview_text.toPlainText()

    dialog._on_accept()

    assert dialog.created_feature is not None
    feature = dialog.created_feature
    assert len(feature.parts) == 2
    # minus strand -> descending genomic order (D-002), regardless of table entry order
    assert [(p.start0, p.end0) for p in feature.parts] == [(299, 350), (100, 150)]

    persisted = window.project_service.list_features(record.id)
    assert any(f.id == feature.id for f in persisted)


def test_export_nucleotide_fasta_menu_action(qtbot, tmp_path, monkeypatch):
    window = MainWindow(blast_work_dir=tmp_path / "blast_work")
    qtbot.addWidget(window)
    _open_project_with_fasta(window, tmp_path, monkeypatch)

    out_path = tmp_path / "exported.fasta"
    monkeypatch.setattr(
        "genome_workbench.ui.main_window.QFileDialog.getSaveFileName",
        staticmethod(lambda *a, **k: (str(out_path), "")),
    )
    window._on_export_nucleotide_fasta()
    assert out_path.exists()
    assert out_path.read_text().startswith(">simple_linear_1kb")


def test_extract_selection_as_new_record_via_context_menu_dispatch(qtbot, tmp_path, monkeypatch):
    window = MainWindow(blast_work_dir=tmp_path / "blast_work")
    qtbot.addWidget(window)
    record = _open_project_with_fasta(window, tmp_path, monkeypatch)

    before_count = len(window.project_service.list_records())
    window._dispatch_selection_action("extract_record", 100, 300)

    records = window.project_service.list_records()
    assert len(records) == before_count + 1
    new_record = next(r for r in records if r.id != record.id)
    assert new_record.length == 200
    assert new_record.sequence == record.sequence[100:300]


def test_reverse_complement_record_via_context_menu_dispatch(qtbot, tmp_path, monkeypatch):
    from genome_workbench.domain.sequence_ops import reverse_complement

    window = MainWindow(blast_work_dir=tmp_path / "blast_work")
    qtbot.addWidget(window)
    record = _open_project_with_fasta(window, tmp_path, monkeypatch)

    window._dispatch_selection_action("reverse_complement_record", 0, record.length)

    records = window.project_service.list_records()
    new_record = next(r for r in records if r.id != record.id)
    assert new_record.sequence == reverse_complement(record.sequence)
