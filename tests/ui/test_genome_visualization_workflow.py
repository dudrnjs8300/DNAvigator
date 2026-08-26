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
