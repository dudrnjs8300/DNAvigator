"""Fuzzy (GenBank </>) location boundaries: previously the domain/adapters
fully supported fuzzy_start/fuzzy_end and preserved them on import, but there
was no UI to actually create or edit one (KNOWN_LIMITATIONS.md gap). Covers
both creation (AddFeatureDialog) and re-editing (InspectorDock).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import Qt

from genome_workbench.domain.qualifiers import QualifierSet
from genome_workbench.ui.dialogs.add_feature_dialog import AddFeatureDialog
from genome_workbench.ui.docks.inspector_dock import InspectorDock
from genome_workbench.ui.main_window import MainWindow

pytestmark = pytest.mark.ui

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


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


# -- AddFeatureDialog: creating a new feature with fuzzy boundaries ----------


def test_simple_feature_created_with_fuzzy_start(qtbot, tmp_path, monkeypatch):
    window = MainWindow(blast_work_dir=tmp_path / "blast_work")
    qtbot.addWidget(window)
    record = _open_project_with_fasta(window, tmp_path, monkeypatch)

    dialog = AddFeatureDialog(record, window.annotation_service, window)
    qtbot.addWidget(dialog)
    dialog._start_spin.setValue(101)
    dialog._end_spin.setValue(200)
    dialog._fuzzy_start_check.setChecked(True)

    dialog._on_accept()

    assert dialog.created_feature is not None
    part = dialog.created_feature.parts[0]
    assert part.fuzzy_start is True
    assert part.fuzzy_end is False


def test_simple_feature_created_with_fuzzy_end(qtbot, tmp_path, monkeypatch):
    window = MainWindow(blast_work_dir=tmp_path / "blast_work")
    qtbot.addWidget(window)
    record = _open_project_with_fasta(window, tmp_path, monkeypatch)

    dialog = AddFeatureDialog(record, window.annotation_service, window)
    qtbot.addWidget(dialog)
    dialog._start_spin.setValue(101)
    dialog._end_spin.setValue(200)
    dialog._fuzzy_end_check.setChecked(True)

    dialog._on_accept()

    part = dialog.created_feature.parts[0]
    assert part.fuzzy_start is False
    assert part.fuzzy_end is True


def test_compound_feature_created_with_per_segment_fuzzy_flags(qtbot, tmp_path, monkeypatch):
    window = MainWindow(blast_work_dir=tmp_path / "blast_work")
    qtbot.addWidget(window)
    record = _open_project_with_fasta(window, tmp_path, monkeypatch)

    dialog = AddFeatureDialog(record, window.annotation_service, window)
    qtbot.addWidget(dialog)
    dialog._join_checkbox.setChecked(True)
    dialog._segments_table.setRowCount(0)
    dialog._add_segment_row(101, 200, fuzzy_start=True, fuzzy_end=False)
    dialog._add_segment_row(301, 400, fuzzy_start=False, fuzzy_end=True)

    dialog._on_accept()

    assert dialog.created_feature is not None
    parts_by_start = sorted(dialog.created_feature.parts, key=lambda p: p.start0)
    assert parts_by_start[0].fuzzy_start is True
    assert parts_by_start[0].fuzzy_end is False
    assert parts_by_start[1].fuzzy_start is False
    assert parts_by_start[1].fuzzy_end is True


def test_default_segments_are_not_fuzzy(qtbot, tmp_path, monkeypatch):
    window = MainWindow(blast_work_dir=tmp_path / "blast_work")
    qtbot.addWidget(window)
    record = _open_project_with_fasta(window, tmp_path, monkeypatch)

    dialog = AddFeatureDialog(record, window.annotation_service, window)
    qtbot.addWidget(dialog)
    dialog._on_accept()

    part = dialog.created_feature.parts[0]
    assert part.fuzzy_start is False
    assert part.fuzzy_end is False


# -- InspectorDock: re-editing an existing feature's fuzzy boundaries -------


def test_inspector_populates_fuzzy_checkboxes_from_existing_simple_feature(
    qtbot, tmp_path, monkeypatch
):
    window = MainWindow(blast_work_dir=tmp_path / "blast_work")
    qtbot.addWidget(window)
    record = _open_project_with_fasta(window, tmp_path, monkeypatch)

    feature = window.annotation_service.create_simple_feature(
        record,
        101,
        200,
        1,
        "misc_feature",
        QualifierSet.from_pairs([]),
        fuzzy_start=True,
        fuzzy_end=False,
    )
    window._refresh_features_only()
    window._on_feature_selected_from_view(feature.id)

    inspector: InspectorDock = window.inspector_dock
    assert inspector._fuzzy_start_check.isChecked()
    assert not inspector._fuzzy_end_check.isChecked()


def test_inspector_apply_preserves_fuzzy_flags_unchanged(qtbot, tmp_path, monkeypatch):
    window = MainWindow(blast_work_dir=tmp_path / "blast_work")
    qtbot.addWidget(window)
    record = _open_project_with_fasta(window, tmp_path, monkeypatch)

    feature = window.annotation_service.create_simple_feature(
        record,
        101,
        200,
        1,
        "misc_feature",
        QualifierSet.from_pairs([]),
        fuzzy_start=True,
        fuzzy_end=True,
    )
    window._refresh_features_only()
    window._on_feature_selected_from_view(feature.id)

    inspector: InspectorDock = window.inspector_dock
    inspector._on_apply()

    reloaded = window.project_service.get_repository().get_feature(feature.id)
    assert reloaded.parts[0].fuzzy_start is True
    assert reloaded.parts[0].fuzzy_end is True


def test_inspector_can_toggle_fuzzy_flag_on_and_apply(qtbot, tmp_path, monkeypatch):
    window = MainWindow(blast_work_dir=tmp_path / "blast_work")
    qtbot.addWidget(window)
    record = _open_project_with_fasta(window, tmp_path, monkeypatch)

    feature = window.annotation_service.create_simple_feature(
        record, 101, 200, 1, "misc_feature", QualifierSet.from_pairs([])
    )
    window._refresh_features_only()
    window._on_feature_selected_from_view(feature.id)

    inspector: InspectorDock = window.inspector_dock
    assert not inspector._fuzzy_start_check.isChecked()
    inspector._fuzzy_start_check.setChecked(True)
    inspector._on_apply()

    reloaded = window.project_service.get_repository().get_feature(feature.id)
    assert reloaded.parts[0].fuzzy_start is True


def test_inspector_populates_and_preserves_per_segment_fuzzy_flags_for_join_feature(
    qtbot, tmp_path, monkeypatch
):
    window = MainWindow(blast_work_dir=tmp_path / "blast_work")
    qtbot.addWidget(window)
    record = _open_project_with_fasta(window, tmp_path, monkeypatch)

    feature = window.annotation_service.create_compound_feature(
        record,
        [(101, 200, True, False), (301, 400, False, True)],
        1,
        "CDS",
        QualifierSet.from_pairs([]),
    )
    window._refresh_features_only()
    window._on_feature_selected_from_view(feature.id)

    inspector: InspectorDock = window.inspector_dock
    assert inspector._segments_table.item(0, 2).checkState() == Qt.CheckState.Checked
    assert inspector._segments_table.item(0, 3).checkState() == Qt.CheckState.Unchecked
    assert inspector._segments_table.item(1, 2).checkState() == Qt.CheckState.Unchecked
    assert inspector._segments_table.item(1, 3).checkState() == Qt.CheckState.Checked

    inspector._on_apply()

    reloaded = window.project_service.get_repository().get_feature(feature.id)
    parts_by_start = sorted(reloaded.parts, key=lambda p: p.start0)
    assert parts_by_start[0].fuzzy_start is True
    assert parts_by_start[0].fuzzy_end is False
    assert parts_by_start[1].fuzzy_start is False
    assert parts_by_start[1].fuzzy_end is True
