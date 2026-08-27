"""Copy a genomic region (Ctrl+C on Genome Map / Circular Map) and paste it
as a new record, annotations included, by selecting a destination in
Project Explorer and pressing Ctrl+V (user-reported gap: the existing
"Extract Selection as New Record" menu action silently dropped every
feature, and there was no copy/paste path into a specific folder at all).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QMessageBox

from genome_workbench.domain.locations import LocationPart
from genome_workbench.domain.models import Feature, MoleculeType, SequenceRecord, Topology
from genome_workbench.domain.qualifiers import QualifierSet
from genome_workbench.ui.main_window import MainWindow

pytestmark = pytest.mark.ui


def _copy_key_event() -> QKeyEvent:
    return QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier, "c")


def _paste_key_event() -> QKeyEvent:
    return QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier, "v")


def _setup_window_with_record(tmp_path: Path) -> tuple[MainWindow, SequenceRecord]:
    window = MainWindow(blast_work_dir=tmp_path / "blast_work")
    window.project_service.create_new(tmp_path / "proj.gwbproj", "Copy Paste Test")
    record = SequenceRecord(
        display_id="source",
        sequence="ACGT" * 250,  # 1000 bp
        checksum_sha256="x",
        molecule_type=MoleculeType.DNA,
        topology=Topology.LINEAR,
    )
    repo = window.project_service.get_repository()
    repo.save_record(record)
    inside = Feature(
        record_id=record.id,
        type="CDS",
        strand=1,
        parts=[LocationPart(start0=110, end0=140, order_index=0)],
        qualifiers=QualifierSet.from_pairs([("gene", "insideGene")]),
    )
    outside = Feature(
        record_id=record.id,
        type="CDS",
        strand=1,
        parts=[LocationPart(start0=500, end0=530, order_index=0)],
        qualifiers=QualifierSet.from_pairs([("gene", "outsideGene")]),
    )
    repo.save_feature(inside)
    repo.save_feature(outside)
    window._on_record_selected(record.id)
    return window, record


def test_ctrl_c_then_ctrl_v_pastes_region_with_only_the_features_inside_it(qtbot, tmp_path: Path):
    window, record = _setup_window_with_record(tmp_path)
    qtbot.addWidget(window)

    canvas = window.genome_map_page.canvas
    canvas.set_viewport(0, 1000)
    canvas._selection = (100, 200)  # covers insideGene (110-140), not outsideGene (500-530)
    canvas.keyPressEvent(_copy_key_event())

    assert window._region_clipboard == (record.id, 100, 200, 1)

    window.explorer_dock._on_paste_key_pressed()

    records = window.project_service.list_records()
    new_records = [r for r in records if r.id != record.id]
    assert len(new_records) == 1
    new_record = new_records[0]
    assert new_record.sequence == record.sequence[100:200]

    new_features = window.project_service.list_features(new_record.id)
    assert len(new_features) == 1
    assert new_features[0].qualifiers.get_first("gene") == "insideGene"
    # rebased: 110-100=10, 140-100=40
    assert (new_features[0].start0, new_features[0].end0) == (10, 40)


def test_paste_places_new_record_into_the_selected_folder(qtbot, tmp_path: Path):
    window, record = _setup_window_with_record(tmp_path)
    qtbot.addWidget(window)
    folder = window.project_service.create_folder("Extracted")
    window._refresh_project_explorer()

    canvas = window.genome_map_page.canvas
    canvas.set_viewport(0, 1000)
    canvas._selection = (0, 50)
    canvas.keyPressEvent(_copy_key_event())

    # select the folder item in the tree
    folder_item = next(
        window.explorer_dock._tree.topLevelItem(i)
        for i in range(window.explorer_dock._tree.topLevelItemCount())
        if window.explorer_dock._tree.topLevelItem(i).text(0) == "Extracted"
    )
    window.explorer_dock._tree.setCurrentItem(folder_item)

    window.explorer_dock._on_paste_key_pressed()

    new_records = [r for r in window.project_service.list_records() if r.id != record.id]
    assert len(new_records) == 1
    assert new_records[0].folder_id == folder.id


def test_paste_places_new_record_into_folder_of_selected_record(qtbot, tmp_path: Path):
    window, record = _setup_window_with_record(tmp_path)
    qtbot.addWidget(window)
    folder = window.project_service.create_folder("Isolates")
    window.project_service.move_record_to_folder(record.id, folder.id)
    window._refresh_project_explorer()

    canvas = window.genome_map_page.canvas
    canvas.set_viewport(0, 1000)
    canvas._selection = (0, 50)
    canvas.keyPressEvent(_copy_key_event())

    # select the record itself (which lives inside "Isolates")
    record_item = next(
        item for item in window.explorer_dock._iter_all_items() if item.text(0) == record.display_id
    )
    window.explorer_dock._tree.setCurrentItem(record_item)

    window.explorer_dock._on_paste_key_pressed()

    new_records = [r for r in window.project_service.list_records() if r.id not in (record.id,)]
    assert len(new_records) == 1
    assert new_records[0].folder_id == folder.id


def test_paste_with_nothing_copied_does_nothing(qtbot, tmp_path: Path):
    window, record = _setup_window_with_record(tmp_path)
    qtbot.addWidget(window)
    assert window._region_clipboard is None

    window.explorer_dock._on_paste_key_pressed()

    assert window.project_service.list_records() == [record]


def test_paste_after_source_record_deleted_warns_instead_of_crashing(
    qtbot, tmp_path: Path, monkeypatch
):
    window, record = _setup_window_with_record(tmp_path)
    qtbot.addWidget(window)

    canvas = window.genome_map_page.canvas
    canvas.set_viewport(0, 1000)
    canvas._selection = (0, 50)
    canvas.keyPressEvent(_copy_key_event())

    window.project_service.delete_record(record.id)
    window._refresh_project_explorer()

    warning_calls = []
    monkeypatch.setattr(
        "genome_workbench.ui.main_window.QMessageBox.warning",
        staticmethod(lambda *a, **k: warning_calls.append(a) or QMessageBox.StandardButton.Ok),
    )

    window.explorer_dock._on_paste_key_pressed()  # must not raise

    assert warning_calls


def test_circular_canvas_ctrl_c_also_sets_the_region_clipboard(qtbot, tmp_path: Path):
    window, record = _setup_window_with_record(tmp_path)
    qtbot.addWidget(window)
    feature = Feature(
        record_id=record.id,
        type="CDS",
        strand=1,
        parts=[LocationPart(start0=10, end0=20, order_index=0)],
    )
    window.project_service.get_repository().save_feature(feature)
    window._refresh_features_only()

    circular = window.circular_canvas
    circular.set_record(record, window.project_service.list_features(record.id))
    circular.select_feature(feature.id)
    circular.keyPressEvent(_copy_key_event())

    assert window._region_clipboard == (record.id, 10, 20, 1)
