"""Qt UI smoke tests via pytest-qt. Dialog-blocking static methods are
monkeypatched to return fixed paths so the whole flow runs headless.
"""

from pathlib import Path

import pytest

from genome_workbench.domain.qualifiers import QualifierSet
from genome_workbench.ui.main_window import MainWindow
from genome_workbench.version import APP_NAME

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"

pytestmark = pytest.mark.ui


def test_main_window_launches_empty(qtbot, tmp_path):
    window = MainWindow(blast_work_dir=tmp_path / "blast_work")
    qtbot.addWidget(window)
    assert APP_NAME in window.windowTitle()
    assert not window.project_service.is_open
    assert not window.action_add_feature.isEnabled()
    assert not window.action_export_genbank.isEnabled()
    # the central widget is the visualization, not a text/table view
    assert window._tabs.count() == 4
    assert window._tabs.tabText(0) == "Genome Map"
    assert window._tabs.tabText(1) == "Circular Map"
    assert window._tabs.tabText(2) == "Feature Table"
    assert window._tabs.tabText(3) == "Alignment View"


def test_blast_menu_actions_are_enabled_and_never_crash_without_blast_installed(qtbot, tmp_path):
    window = MainWindow(blast_work_dir=tmp_path / "blast_work")
    qtbot.addWidget(window)
    menus = [action.menu() for action in window.menuBar().actions() if action.menu()]
    blast_menus = [m for m in menus if m.title() == "&BLAST"]
    assert len(blast_menus) == 1
    # setup/create-database entry points must always be reachable (never hidden),
    # since a missing BLAST+ installation must be discoverable/explainable, not silent
    for action in blast_menus[0].actions():
        assert action.isEnabled()
    assert not window._blast_installation.is_fully_installed()
    assert window.blast_service.detect_installation() is not None  # never raises


def test_new_project_import_fasta_add_feature_save_reopen(qtbot, tmp_path, monkeypatch):
    project_path = str(tmp_path / "ui_flow" / "project.gwbproj")
    fasta_path = str(FIXTURES_DIR / "simple_linear.fasta")

    window = MainWindow(blast_work_dir=tmp_path / "blast_work")
    qtbot.addWidget(window)

    monkeypatch.setattr(
        "genome_workbench.ui.main_window.QFileDialog.getSaveFileName",
        staticmethod(lambda *a, **k: (project_path, "")),
    )
    monkeypatch.setattr(
        "genome_workbench.ui.main_window.QInputDialog.getText",
        staticmethod(lambda *a, **k: ("UI Flow Project", True)),
    )
    window._on_new_project()
    assert window.project_service.is_open

    monkeypatch.setattr(
        "genome_workbench.ui.main_window.QFileDialog.getOpenFileName",
        staticmethod(lambda *a, **k: (fasta_path, "")),
    )
    window._on_import_fasta()
    records = window.project_service.list_records()
    assert len(records) == 1

    # importing auto-selects the first record, and the genome map canvas
    # must actually be populated (not just a list entry)
    assert window._current_record is not None
    assert window.genome_map_page.canvas._record is not None
    assert window.genome_map_page.canvas._record.id == records[0].id
    assert window.genome_map_page.canvas.viewport_transform is not None
    assert window.circular_canvas._record is not None

    def _fake_exec(self):
        self.created_feature = self._annotation_service.create_simple_feature(
            self._record,
            101,
            900,
            1,
            "CDS",
            QualifierSet.from_pairs([("gene", "exampleA")]),
        )
        return 1

    monkeypatch.setattr(
        "genome_workbench.ui.dialogs.add_feature_dialog.AddFeatureDialog.exec", _fake_exec
    )
    window._on_add_feature()
    features = window.project_service.list_features(records[0].id)
    assert len(features) == 1
    assert window.feature_table.rowCount() == 1

    # feature-table -> canvas/inspector sync
    window._on_feature_selected_from_view(features[0].id)
    assert window._current_feature is not None
    assert window._current_feature.id == features[0].id
    assert window.genome_map_page.canvas._selected_feature_id == features[0].id
    assert window.circular_canvas._selected_feature_id == features[0].id

    window.project_service.close()
    window.project_service.open(Path(project_path))
    reopened_records = window.project_service.list_records()
    reopened_features = window.project_service.list_features(reopened_records[0].id)
    assert len(reopened_features) == 1
    window.project_service.close()


def test_export_gff3_and_import_gff3_menu_actions(qtbot, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    project_path = str(tmp_path / "gff3_flow" / "project.gwbproj")
    fasta_path = str(FIXTURES_DIR / "simple_linear.fasta")
    gff3_out_path = str(tmp_path / "gff3_flow" / "export.gff3")

    window = MainWindow(blast_work_dir=tmp_path / "blast_work")
    qtbot.addWidget(window)

    monkeypatch.setattr(
        "genome_workbench.ui.main_window.QFileDialog.getSaveFileName",
        staticmethod(lambda *a, **k: (project_path, "")),
    )
    monkeypatch.setattr(
        "genome_workbench.ui.main_window.QInputDialog.getText",
        staticmethod(lambda *a, **k: ("GFF3 Flow", True)),
    )
    window._on_new_project()

    monkeypatch.setattr(
        "genome_workbench.ui.main_window.QFileDialog.getOpenFileName",
        staticmethod(lambda *a, **k: (fasta_path, "")),
    )
    window._on_import_fasta()
    record = window.project_service.list_records()[0]
    window.annotation_service.create_simple_feature(
        record, 101, 900, 1, "CDS", QualifierSet.from_pairs([("gene", "gffTest")])
    )

    monkeypatch.setattr(
        "genome_workbench.ui.main_window.QMessageBox.question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes),
    )
    monkeypatch.setattr(
        "genome_workbench.ui.main_window.QFileDialog.getSaveFileName",
        staticmethod(lambda *a, **k: (gff3_out_path, "")),
    )
    window._on_export_gff3()
    assert Path(gff3_out_path).exists()

    second_project_path = str(tmp_path / "gff3_flow" / "reimport.gwbproj")
    monkeypatch.setattr(
        "genome_workbench.ui.main_window.QFileDialog.getSaveFileName",
        staticmethod(lambda *a, **k: (second_project_path, "")),
    )
    window._on_new_project()

    monkeypatch.setattr(
        "genome_workbench.ui.main_window.QFileDialog.getOpenFileName",
        staticmethod(lambda *a, **k: (gff3_out_path, "")),
    )
    window._on_import_gff3()
    reimported_records = window.project_service.list_records()
    assert len(reimported_records) == 1
    reimported_features = window.project_service.list_features(reimported_records[0].id)
    assert len(reimported_features) == 1
    assert reimported_features[0].qualifiers.get_first("gene") == "gffTest"
    window.project_service.close()


def test_open_locked_project_offers_read_only_via_ui(qtbot, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    from genome_workbench.application.project_service import ProjectService

    project_path = tmp_path / "locked" / "project.gwbproj"
    other_instance = ProjectService()
    other_instance.create_new(project_path, "Other Instance")

    window = MainWindow(blast_work_dir=tmp_path / "blast_work")
    qtbot.addWidget(window)

    monkeypatch.setattr(
        "genome_workbench.ui.main_window.QFileDialog.getOpenFileName",
        staticmethod(lambda *a, **k: (str(project_path), "")),
    )
    monkeypatch.setattr(
        "genome_workbench.ui.main_window.QMessageBox.warning",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Open),
    )
    window._on_open_project()

    assert window.project_service.is_open
    assert window.project_service.is_read_only
    assert not window.action_add_feature.isEnabled()
    assert not window.action_import_fasta.isEnabled()

    window.project_service.close()
    other_instance.close()


def test_open_project_at_path_used_for_startup_file_association(qtbot, tmp_path):
    """MainWindow.open_project_at_path is what genome_workbench.app.run_app
    calls when launched with a project path (e.g. Windows passing %1 when a
    .gwbproj file is double-clicked via the installer's file association) --
    this is the same code path _on_open_project uses after its file dialog,
    exercised directly without a dialog in the loop."""
    from genome_workbench.application.project_service import ProjectService

    project_path = tmp_path / "startup" / "project.gwbproj"
    setup_service = ProjectService()
    setup_service.create_new(project_path, "Startup Project")
    setup_service.close()

    window = MainWindow(blast_work_dir=tmp_path / "blast_work")
    qtbot.addWidget(window)

    window.open_project_at_path(str(project_path))

    assert window.project_service.is_open
    assert not window.project_service.is_read_only
