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


def test_main_window_launches_empty(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    assert APP_NAME in window.windowTitle()
    assert not window.project_service.is_open
    assert not window.action_add_feature.isEnabled()
    assert not window.action_export_genbank.isEnabled()


def test_blast_menu_actions_are_disabled_placeholders(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    menus = [action.menu() for action in window.menuBar().actions() if action.menu()]
    blast_menus = [m for m in menus if m.title() == "&BLAST"]
    assert len(blast_menus) == 1
    assert blast_menus[0].actions()
    for action in blast_menus[0].actions():
        assert not action.isEnabled()


def test_new_project_import_fasta_add_feature_save_reopen(qtbot, tmp_path, monkeypatch):
    project_path = str(tmp_path / "ui_flow" / "project.gwbproj")
    fasta_path = str(FIXTURES_DIR / "simple_linear.fasta")

    window = MainWindow()
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

    window._on_record_selected(records[0].id)
    assert window._current_record is not None
    assert window._sequence_view.current_record is not None

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
    assert window._feature_table.rowCount() == 1

    window.project_service.close()
    window.project_service.open(Path(project_path))
    reopened_records = window.project_service.list_records()
    reopened_features = window.project_service.list_features(reopened_records[0].id)
    assert len(reopened_features) == 1
    window.project_service.close()
