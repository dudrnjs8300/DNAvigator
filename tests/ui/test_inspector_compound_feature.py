"""Inspector re-editing of compound (join) features.

Before this, InspectorDock always built a single-part SIMPLE feature on
Apply regardless of what was selected -- opening a join feature and clicking
Apply (even without touching anything) silently collapsed it to a
bounding-box simple feature. These tests guard against that regression and
exercise real multi-segment editing through the same segments-table pattern
AddFeatureDialog uses.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from genome_workbench.domain.locations import LocationOperator
from genome_workbench.domain.qualifiers import QualifierSet
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


def test_opening_join_feature_prechecks_join_mode_and_populates_segments(
    qtbot, tmp_path, monkeypatch
):
    window = MainWindow(blast_work_dir=tmp_path / "blast_work")
    qtbot.addWidget(window)
    record = _open_project_with_fasta(window, tmp_path, monkeypatch)

    feature = window.annotation_service.create_compound_feature(
        record, [(101, 200), (301, 400)], 1, "CDS", QualifierSet.from_pairs([("gene", "spliced")])
    )
    window._refresh_features_only()
    window._on_feature_selected_from_view(feature.id)

    inspector: InspectorDock = window.inspector_dock
    assert inspector._join_checkbox.isChecked()
    assert inspector._location_stack.currentIndex() == 1
    assert inspector._segments_table.rowCount() == 2
    assert inspector._segments_table.item(0, 0).text() == "101"
    assert inspector._segments_table.item(0, 1).text() == "200"
    assert inspector._segments_table.item(1, 0).text() == "301"
    assert inspector._segments_table.item(1, 1).text() == "400"


def test_apply_without_changes_preserves_join_structure(qtbot, tmp_path, monkeypatch):
    """Regression test for the exact bug this session fixed: opening a
    compound feature and clicking Apply used to silently collapse it."""
    window = MainWindow(blast_work_dir=tmp_path / "blast_work")
    qtbot.addWidget(window)
    record = _open_project_with_fasta(window, tmp_path, monkeypatch)

    feature = window.annotation_service.create_compound_feature(
        record, [(101, 200), (301, 400)], 1, "CDS", QualifierSet.from_pairs([("gene", "spliced")])
    )
    window._refresh_features_only()
    window._on_feature_selected_from_view(feature.id)

    inspector: InspectorDock = window.inspector_dock
    inspector._on_apply()

    reloaded = window.project_service.get_repository().get_feature(feature.id)
    assert reloaded.location_operator == LocationOperator.JOIN
    assert len(reloaded.parts) == 2
    assert [(p.start0, p.end0) for p in reloaded.parts] == [(100, 200), (300, 400)]


def test_editing_a_segment_value_updates_the_saved_feature(qtbot, tmp_path, monkeypatch):
    window = MainWindow(blast_work_dir=tmp_path / "blast_work")
    qtbot.addWidget(window)
    record = _open_project_with_fasta(window, tmp_path, monkeypatch)

    feature = window.annotation_service.create_compound_feature(
        record, [(101, 200), (301, 400)], 1, "CDS", QualifierSet.from_pairs([])
    )
    window._refresh_features_only()
    window._on_feature_selected_from_view(feature.id)

    inspector: InspectorDock = window.inspector_dock
    inspector._segments_table.item(1, 1).setText("450")  # extend second segment's end
    inspector._on_apply()

    reloaded = window.project_service.get_repository().get_feature(feature.id)
    assert [(p.start0, p.end0) for p in reloaded.parts] == [(100, 200), (300, 450)]


def test_adding_a_third_segment_via_inspector(qtbot, tmp_path, monkeypatch):
    window = MainWindow(blast_work_dir=tmp_path / "blast_work")
    qtbot.addWidget(window)
    record = _open_project_with_fasta(window, tmp_path, monkeypatch)

    feature = window.annotation_service.create_compound_feature(
        record, [(101, 200), (301, 400)], 1, "CDS", QualifierSet.from_pairs([])
    )
    window._refresh_features_only()
    window._on_feature_selected_from_view(feature.id)

    inspector: InspectorDock = window.inspector_dock
    inspector._add_segment_row(501, 600)
    inspector._on_apply()

    reloaded = window.project_service.get_repository().get_feature(feature.id)
    assert len(reloaded.parts) == 3
    assert [(p.start0, p.end0) for p in reloaded.parts] == [(100, 200), (300, 400), (500, 600)]


def test_reverse_strand_join_feature_orders_parts_biologically(qtbot, tmp_path, monkeypatch):
    """D-002: for minus-strand compound features, order_index must be
    descending genomic order (5'->3' biological order), not ascending."""
    window = MainWindow(blast_work_dir=tmp_path / "blast_work")
    qtbot.addWidget(window)
    record = _open_project_with_fasta(window, tmp_path, monkeypatch)

    feature = window.annotation_service.create_compound_feature(
        record, [(101, 200), (301, 400)], -1, "CDS", QualifierSet.from_pairs([])
    )
    window._refresh_features_only()
    window._on_feature_selected_from_view(feature.id)

    inspector: InspectorDock = window.inspector_dock
    # segments table still displays ascending genomic order for readability
    assert inspector._segments_table.item(0, 0).text() == "101"
    assert inspector._segments_table.item(1, 0).text() == "301"

    inspector._on_apply()  # no changes -- must preserve biological order on save

    reloaded = window.project_service.get_repository().get_feature(feature.id)
    ordered_by_index = sorted(reloaded.parts, key=lambda p: p.order_index)
    # descending genomic order = biological 5'->3' order for minus strand
    assert [(p.start0, p.end0) for p in ordered_by_index] == [(300, 400), (100, 200)]


def test_unchecking_join_collapses_to_simple_feature(qtbot, tmp_path, monkeypatch):
    window = MainWindow(blast_work_dir=tmp_path / "blast_work")
    qtbot.addWidget(window)
    record = _open_project_with_fasta(window, tmp_path, monkeypatch)

    feature = window.annotation_service.create_compound_feature(
        record, [(101, 200), (301, 400)], 1, "CDS", QualifierSet.from_pairs([])
    )
    window._refresh_features_only()
    window._on_feature_selected_from_view(feature.id)

    inspector: InspectorDock = window.inspector_dock
    inspector._join_checkbox.setChecked(False)
    inspector._on_apply()

    reloaded = window.project_service.get_repository().get_feature(feature.id)
    assert reloaded.location_operator == LocationOperator.SIMPLE
    assert len(reloaded.parts) == 1
    # collapses to the bounding span, seeded into the simple start/end fields
    assert (reloaded.parts[0].start0, reloaded.parts[0].end0) == (100, 400)


def test_checking_join_on_simple_feature_converts_it(qtbot, tmp_path, monkeypatch):
    window = MainWindow(blast_work_dir=tmp_path / "blast_work")
    qtbot.addWidget(window)
    record = _open_project_with_fasta(window, tmp_path, monkeypatch)

    feature = window.annotation_service.create_simple_feature(
        record, 101, 200, 1, "CDS", QualifierSet.from_pairs([])
    )
    window._refresh_features_only()
    window._on_feature_selected_from_view(feature.id)

    inspector: InspectorDock = window.inspector_dock
    assert not inspector._join_checkbox.isChecked()

    inspector._join_checkbox.setChecked(True)
    inspector._add_segment_row(301, 400)
    inspector._on_apply()

    reloaded = window.project_service.get_repository().get_feature(feature.id)
    assert reloaded.location_operator == LocationOperator.JOIN
    assert len(reloaded.parts) == 2


def test_apply_refused_when_segment_end_before_start(qtbot, tmp_path, monkeypatch):
    window = MainWindow(blast_work_dir=tmp_path / "blast_work")
    qtbot.addWidget(window)
    record = _open_project_with_fasta(window, tmp_path, monkeypatch)

    feature = window.annotation_service.create_compound_feature(
        record, [(101, 200), (301, 400)], 1, "CDS", QualifierSet.from_pairs([])
    )
    window._refresh_features_only()
    window._on_feature_selected_from_view(feature.id)

    inspector: InspectorDock = window.inspector_dock
    inspector._segments_table.item(1, 1).setText("250")  # end (250) < start (301)

    received = {}
    inspector.featureUpdateRequested.connect(
        lambda before, after: received.setdefault("after", after)
    )
    inspector._on_apply()

    assert "after" not in received
    unchanged = window.project_service.get_repository().get_feature(feature.id)
    assert len(unchanged.parts) == 2  # nothing was saved
