"""Project Explorer tree support for Alignment items -- same tree-nesting +
dispatch-split pattern as test_project_explorer_folders.py (QMenu.exec()
itself can't be monkeypatched, see D-008, so these drive
_dispatch_alignment_action directly).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox

from genome_workbench.domain.models import Alignment, Folder, MoleculeType
from genome_workbench.ui.docks.project_explorer_dock import ProjectExplorerDock
from genome_workbench.ui.main_window import MainWindow

pytestmark = pytest.mark.ui

_ITEM_TYPE_ROLE = Qt.ItemDataRole.UserRole + 1


def _alignment(name: str, folder_id: str | None = None) -> Alignment:
    return Alignment(name=name, molecule_type=MoleculeType.DNA, length=10, folder_id=folder_id)


def test_set_data_nests_alignments_under_their_folder(qtbot):
    dock = ProjectExplorerDock()
    qtbot.addWidget(dock)

    folder = Folder(name="Isolates")
    in_folder = _alignment("msa_in_folder", folder_id=folder.id)
    at_root = _alignment("msa_at_root")

    dock.set_data([], [folder], alignments=[in_folder, at_root])

    assert dock._tree.topLevelItemCount() == 2  # "Isolates" folder + root-level alignment
    folder_item = next(
        dock._tree.topLevelItem(i)
        for i in range(dock._tree.topLevelItemCount())
        if dock._tree.topLevelItem(i).data(0, _ITEM_TYPE_ROLE) == "folder"
    )
    assert folder_item.childCount() == 1
    assert folder_item.child(0).data(0, _ITEM_TYPE_ROLE) == "alignment"
    assert folder_item.child(0).data(0, Qt.ItemDataRole.UserRole) == in_folder.id


def test_alignment_row_shows_length_and_sequence_count(qtbot):
    dock = ProjectExplorerDock()
    qtbot.addWidget(dock)
    alignment = _alignment("msa1")

    dock.set_data([], [], alignments=[alignment], alignment_sequence_counts={alignment.id: 5})

    item = dock._tree.topLevelItem(0)
    assert item.text(0) == "msa1"
    assert item.text(1) == "alignment"
    assert item.text(2) == "10 cols"
    assert item.text(4) == "5 seq"


def test_selecting_alignment_emits_alignment_selected(qtbot):
    dock = ProjectExplorerDock()
    qtbot.addWidget(dock)
    alignment = _alignment("msa1")
    dock.set_data([], [], alignments=[alignment])

    with qtbot.waitSignal(dock.alignmentSelected, timeout=1000) as blocker:
        dock._tree.setCurrentItem(dock._tree.topLevelItem(0))
    assert blocker.args == [alignment.id]


def test_dispatch_rename_alignment_prompts_and_emits(qtbot, monkeypatch):
    dock = ProjectExplorerDock()
    qtbot.addWidget(dock)
    monkeypatch.setattr(
        "genome_workbench.ui.docks.project_explorer_dock.QInputDialog.getText",
        staticmethod(lambda *a, **k: ("renamed", True)),
    )
    with qtbot.waitSignal(dock.renameAlignmentRequested, timeout=1000) as blocker:
        dock._dispatch_alignment_action("rename", "align-1", "old name")
    assert blocker.args == ["align-1", "renamed"]


def test_dispatch_delete_alignment_prompts_and_emits(qtbot, monkeypatch):
    dock = ProjectExplorerDock()
    qtbot.addWidget(dock)
    monkeypatch.setattr(
        "genome_workbench.ui.docks.project_explorer_dock.QMessageBox.warning",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes),
    )
    with qtbot.waitSignal(dock.deleteAlignmentRequested, timeout=1000) as blocker:
        dock._dispatch_alignment_action("delete", "align-1", "msa1")
    assert blocker.args == ["align-1"]


def test_dispatch_delete_alignment_declined_does_not_emit(qtbot, monkeypatch):
    dock = ProjectExplorerDock()
    qtbot.addWidget(dock)
    monkeypatch.setattr(
        "genome_workbench.ui.docks.project_explorer_dock.QMessageBox.warning",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Cancel),
    )
    received = []
    dock.deleteAlignmentRequested.connect(received.append)
    dock._dispatch_alignment_action("delete", "align-1", "msa1")
    assert received == []


def test_dispatch_move_alignment_picks_target_folder(qtbot, monkeypatch):
    dock = ProjectExplorerDock()
    qtbot.addWidget(dock)
    folder = Folder(name="Target")
    dock.set_data([], [folder], alignments=[_alignment("msa1")])
    monkeypatch.setattr(
        "genome_workbench.ui.docks.project_explorer_dock.QInputDialog.getItem",
        staticmethod(lambda *a, **k: ("Target", True)),
    )
    with qtbot.waitSignal(dock.moveAlignmentToFolderRequested, timeout=1000) as blocker:
        dock._dispatch_alignment_action("move", "align-1", "msa1")
    assert blocker.args == ["align-1", folder.id]


def test_delete_key_on_selected_alignment_prompts(qtbot, monkeypatch):
    dock = ProjectExplorerDock()
    qtbot.addWidget(dock)
    alignment = _alignment("msa1")
    dock.set_data([], [], alignments=[alignment])
    dock._tree.setCurrentItem(dock._tree.topLevelItem(0))
    monkeypatch.setattr(
        "genome_workbench.ui.docks.project_explorer_dock.QMessageBox.warning",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes),
    )
    with qtbot.waitSignal(dock.deleteAlignmentRequested, timeout=1000) as blocker:
        dock._on_delete_key_pressed()
    assert blocker.args == [alignment.id]


def test_main_window_import_select_rename_move_delete_alignment_flow(qtbot, tmp_path: Path):
    fixtures_dir = Path(__file__).parent.parent / "fixtures"
    window = MainWindow(blast_work_dir=tmp_path / "blast_work")
    qtbot.addWidget(window)
    window.project_service.create_new(tmp_path / "proj.gwbproj", "Alignment Flow Test")

    outcome = window.import_service.import_alignment(fixtures_dir / "sample_alignment.fasta")
    assert len(outcome.alignments) == 1
    alignment_id = outcome.alignments[0].id

    window._on_alignment_selected(alignment_id)
    assert window._current_alignment is not None
    assert window._current_alignment.id == alignment_id
    assert window._tabs.currentWidget() is window.alignment_view_page
    assert window.alignment_view_page.canvas.total_row_count == 3

    folder = window.project_service.create_folder("Alignments")
    window._on_move_alignment_to_folder_requested(alignment_id, folder.id)
    assert window.project_service.get_alignment(alignment_id).folder_id == folder.id

    window._on_rename_alignment_requested(alignment_id, "renamed msa")
    assert window.project_service.get_alignment(alignment_id).name == "renamed msa"

    window._on_delete_alignment_requested(alignment_id)
    assert window.project_service.get_alignment(alignment_id) is None
    assert window._current_alignment is None
    assert window.alignment_view_page.canvas.total_row_count == 0


def test_main_window_gff3_annotation_flow_for_alignment(qtbot, tmp_path: Path):
    fixtures_dir = Path(__file__).parent.parent / "fixtures"
    window = MainWindow(blast_work_dir=tmp_path / "blast_work")
    qtbot.addWidget(window)
    window.project_service.create_new(tmp_path / "proj.gwbproj", "Alignment GFF3 Test")

    outcome = window.import_service.import_alignment(fixtures_dir / "sample_alignment.fasta")
    alignment_id = outcome.alignments[0].id
    window._on_alignment_selected(alignment_id)
    assert window.alignment_view_page.canvas.total_row_count == 3
    # nothing annotated yet
    assert window.project_service.list_alignment_features(alignment_id) == []

    gff_outcome = window.import_service.import_alignment_gff3(
        alignment_id, fixtures_dir / "sample_alignment_annotations.gff3"
    )
    window._refresh_alignment_features()  # mirrors what _on_import_alignment_gff3 does

    assert len(gff_outcome.features) == 2
    stored = window.project_service.list_alignment_features(alignment_id)
    assert len(stored) == 2

    canvas = window.alignment_view_page.canvas
    seq_a = next(
        s
        for s in window.project_service.list_alignment_sequences(alignment_id)
        if s.label == "seqA"
    )
    feature_on_seq_a = next(f for f in stored if f.alignment_sequence_id == seq_a.id)
    assert canvas.feature_by_id(feature_on_seq_a.id) is not None

    window._on_alignment_feature_clicked(feature_on_seq_a.id)
    inspector_text = window.inspector_dock._alignment_feature_view.toPlainText()
    assert "testGene" in inspector_text
    assert "seqA" in inspector_text

    # re-importing replaces rather than accumulates
    window.import_service.import_alignment_gff3(
        alignment_id, fixtures_dir / "sample_alignment_annotations.gff3"
    )
    assert len(window.project_service.list_alignment_features(alignment_id)) == 2


def test_ctrl_f_opens_alignment_search_when_alignment_view_is_active(qtbot, tmp_path: Path):
    fixtures_dir = Path(__file__).parent.parent / "fixtures"
    window = MainWindow(blast_work_dir=tmp_path / "blast_work")
    qtbot.addWidget(window)
    window.project_service.create_new(tmp_path / "proj.gwbproj", "Ctrl+F Alignment Test")
    outcome = window.import_service.import_alignment(fixtures_dir / "sample_alignment.fasta")
    window._on_alignment_selected(outcome.alignments[0].id)
    assert window._tabs.currentWidget() is window.alignment_view_page

    window._on_find_feature_requested()

    assert window._alignment_find_dialog is not None
    assert window._alignment_find_dialog.isVisible()


def test_ctrl_f_opens_genome_feature_search_when_genome_map_is_active(qtbot, tmp_path: Path):
    fixtures_dir = Path(__file__).parent.parent / "fixtures"
    window = MainWindow(blast_work_dir=tmp_path / "blast_work")
    qtbot.addWidget(window)
    window.project_service.create_new(tmp_path / "proj.gwbproj", "Ctrl+F Genome Test")
    window.import_service.import_fasta(fixtures_dir / "simple_linear.fasta")
    window._tabs.setCurrentWidget(window.genome_map_page)

    window._on_find_feature_requested()

    assert window.find_dialog.isVisible()
    assert window._alignment_find_dialog is None


def test_choosing_an_alignment_search_result_jumps_the_view(qtbot, tmp_path: Path):
    fixtures_dir = Path(__file__).parent.parent / "fixtures"
    window = MainWindow(blast_work_dir=tmp_path / "blast_work")
    qtbot.addWidget(window)
    window.project_service.create_new(tmp_path / "proj.gwbproj", "Ctrl+F Jump Test")
    outcome = window.import_service.import_alignment(fixtures_dir / "sample_alignment.fasta")
    alignment_id = outcome.alignments[0].id
    window._on_alignment_selected(alignment_id)
    # shrink so not every row fits on screen -- otherwise scrolling to row 1
    # is a no-op since it (and everything else) is already visible
    window.alignment_view_page.canvas.setFixedHeight(80)
    window.alignment_view_page._sync_scrollbar()
    sequences = window.project_service.list_alignment_sequences(alignment_id)
    target = sequences[1]

    window._on_alignment_find_result_chosen(target.id, 3, 8)

    assert window._tabs.currentWidget() is window.alignment_view_page
    assert window.alignment_view_page.canvas.first_visible_row == 1
    vt = window.alignment_view_page.canvas.viewport_transform
    assert vt.view_start0 <= 3 and vt.view_end0 >= 8
