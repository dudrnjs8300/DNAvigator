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
