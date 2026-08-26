"""Project Explorer folder tree: nested tree building, and the context-menu
dispatch logic for delete/move/create/rename (QMenu.exec() itself can't be
monkeypatched -- see D-008 in docs/DECISIONS.md -- so these tests drive
_dispatch_folder_action/_dispatch_record_action directly, same split pattern
MainWindow's canvas context menu already uses).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox

from genome_workbench.domain.models import Folder, MoleculeType, SequenceRecord, Topology
from genome_workbench.ui.docks.project_explorer_dock import ProjectExplorerDock
from genome_workbench.ui.main_window import MainWindow

pytestmark = pytest.mark.ui

_ITEM_TYPE_ROLE = Qt.ItemDataRole.UserRole + 1


def _record(display_id: str, folder_id: str | None = None) -> SequenceRecord:
    return SequenceRecord(
        display_id=display_id,
        sequence="ACGT" * 10,
        checksum_sha256="x",
        molecule_type=MoleculeType.DNA,
        topology=Topology.LINEAR,
        folder_id=folder_id,
    )


def test_set_data_nests_records_under_their_folder(qtbot):
    dock = ProjectExplorerDock()
    qtbot.addWidget(dock)

    folder = Folder(name="Isolates")
    subfolder = Folder(name="2026 batch", parent_folder_id=folder.id)
    in_folder = _record("contig_in_folder", folder_id=subfolder.id)
    at_root = _record("contig_at_root")

    dock.set_data([in_folder, at_root], [folder, subfolder])

    assert dock._tree.topLevelItemCount() == 2  # "Isolates" folder + root-level record
    folder_item = next(
        dock._tree.topLevelItem(i)
        for i in range(dock._tree.topLevelItemCount())
        if dock._tree.topLevelItem(i).text(0) == "Isolates"
    )
    assert folder_item.childCount() == 1
    subfolder_item = folder_item.child(0)
    assert subfolder_item.text(0) == "2026 batch"
    assert subfolder_item.childCount() == 1
    assert subfolder_item.child(0).text(0) == "contig_in_folder"


def test_set_data_falls_back_to_root_for_orphaned_folder_reference(qtbot):
    dock = ProjectExplorerDock()
    qtbot.addWidget(dock)
    # record references a folder id that no longer exists (deleted folder
    # somehow not cleaned up) -- must not crash, must surface at root
    orphan = _record("orphan", folder_id="does-not-exist")
    dock.set_data([orphan], [])
    assert dock._tree.topLevelItemCount() == 1
    assert dock._tree.topLevelItem(0).text(0) == "orphan"


def test_dispatch_delete_record_confirmed_emits_signal(qtbot, monkeypatch):
    dock = ProjectExplorerDock()
    qtbot.addWidget(dock)
    monkeypatch.setattr(
        "genome_workbench.ui.docks.project_explorer_dock.QMessageBox.warning",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes),
    )
    received = {}
    dock.deleteRecordRequested.connect(lambda rid: received.setdefault("id", rid))

    dock._dispatch_record_action("delete_record", "rec-1", "contig1")

    assert received.get("id") == "rec-1"


def test_dispatch_delete_record_cancelled_emits_nothing(qtbot, monkeypatch):
    dock = ProjectExplorerDock()
    qtbot.addWidget(dock)
    monkeypatch.setattr(
        "genome_workbench.ui.docks.project_explorer_dock.QMessageBox.warning",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Cancel),
    )
    received = {}
    dock.deleteRecordRequested.connect(lambda rid: received.setdefault("id", rid))

    dock._dispatch_record_action("delete_record", "rec-1", "contig1")

    assert "id" not in received


def test_dispatch_new_folder_emits_name_and_parent(qtbot, monkeypatch):
    dock = ProjectExplorerDock()
    qtbot.addWidget(dock)
    monkeypatch.setattr(
        "genome_workbench.ui.docks.project_explorer_dock.QInputDialog.getText",
        staticmethod(lambda *a, **k: ("New Isolates", True)),
    )
    received = {}
    dock.createFolderRequested.connect(
        lambda name, parent: received.setdefault("args", (name, parent))
    )

    dock._dispatch_folder_action("new_folder", "parent-folder-id", "Parent")

    assert received["args"] == ("New Isolates", "parent-folder-id")


def test_dispatch_delete_folder_confirmed_emits_signal(qtbot, monkeypatch):
    dock = ProjectExplorerDock()
    qtbot.addWidget(dock)
    monkeypatch.setattr(
        "genome_workbench.ui.docks.project_explorer_dock.QMessageBox.question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes),
    )
    received = {}
    dock.deleteFolderRequested.connect(lambda fid: received.setdefault("id", fid))

    dock._dispatch_folder_action("delete", "folder-1", "Isolates")

    assert received.get("id") == "folder-1"


def test_dispatch_move_record_picks_target_folder(qtbot, monkeypatch):
    dock = ProjectExplorerDock()
    qtbot.addWidget(dock)
    folder = Folder(name="Isolates")
    dock.set_data([], [folder])
    monkeypatch.setattr(
        "genome_workbench.ui.docks.project_explorer_dock.QInputDialog.getItem",
        staticmethod(lambda *a, **k: ("Isolates", True)),
    )
    received = {}
    dock.moveRecordToFolderRequested.connect(
        lambda rid, fid: received.setdefault("args", (rid, fid))
    )

    dock._dispatch_record_action("move_to_folder", "rec-1", "contig1")

    assert received["args"] == ("rec-1", folder.id)


def test_dispatch_set_linear_and_circular_emit_topology_signal(qtbot):
    dock = ProjectExplorerDock()
    qtbot.addWidget(dock)
    received = []
    dock.topologyChangeRequested.connect(lambda rid, val: received.append((rid, val)))

    dock._dispatch_record_action("set_linear", "rec-1", "contig1")
    dock._dispatch_record_action("set_circular", "rec-1", "contig1")

    assert received == [("rec-1", "linear"), ("rec-1", "circular")]


# -- End-to-end through MainWindow -------------------------------------------

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


def _open_project_with_fasta(window: MainWindow, tmp_path: Path, monkeypatch):
    project_path = str(tmp_path / "proj" / "project.gwbproj")
    monkeypatch.setattr(
        "genome_workbench.ui.main_window.QFileDialog.getSaveFileName",
        staticmethod(lambda *a, **k: (project_path, "")),
    )
    monkeypatch.setattr(
        "genome_workbench.ui.main_window.QInputDialog.getText",
        staticmethod(lambda *a, **k: ("Project", True)),
    )
    window._on_new_project()

    fasta_path = str(FIXTURES_DIR / "simple_linear.fasta")
    monkeypatch.setattr(
        "genome_workbench.ui.main_window.QFileDialog.getOpenFileName",
        staticmethod(lambda *a, **k: (fasta_path, "")),
    )
    window._on_import_fasta()
    return window.project_service.list_records()[0]


def test_delete_record_via_main_window_removes_it_and_clears_current_view(
    qtbot, tmp_path, monkeypatch
):
    window = MainWindow(blast_work_dir=tmp_path / "blast_work")
    qtbot.addWidget(window)
    record = _open_project_with_fasta(window, tmp_path, monkeypatch)
    window._on_record_selected(record.id)
    assert window._current_record is not None

    window._on_delete_record_requested(record.id)

    assert window.project_service.get_record(record.id) is None
    assert window._current_record is None


def test_create_folder_and_move_record_via_main_window(qtbot, tmp_path, monkeypatch):
    window = MainWindow(blast_work_dir=tmp_path / "blast_work")
    qtbot.addWidget(window)
    record = _open_project_with_fasta(window, tmp_path, monkeypatch)

    window._on_create_folder_requested("Isolates", "")
    folder = window.project_service.list_folders()[0]
    assert folder.name == "Isolates"

    window._on_move_record_to_folder_requested(record.id, folder.id)
    moved = window.project_service.get_record(record.id)
    assert moved.folder_id == folder.id

    window._on_move_record_to_folder_requested(record.id, "")
    back = window.project_service.get_record(record.id)
    assert back.folder_id is None


def test_delete_folder_via_main_window_keeps_record(qtbot, tmp_path, monkeypatch):
    window = MainWindow(blast_work_dir=tmp_path / "blast_work")
    qtbot.addWidget(window)
    record = _open_project_with_fasta(window, tmp_path, monkeypatch)

    window._on_create_folder_requested("Isolates", "")
    folder = window.project_service.list_folders()[0]
    window._on_move_record_to_folder_requested(record.id, folder.id)

    window._on_delete_folder_requested(folder.id)

    assert window.project_service.list_folders() == []
    assert window.project_service.get_record(record.id) is not None
