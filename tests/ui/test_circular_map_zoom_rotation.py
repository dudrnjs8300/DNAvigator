"""Real mouse wheel zoom and drag rotation on the circular genome map --
previously the circular map had neither (KNOWN_LIMITATIONS.md gap).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtTest import QTest

from genome_workbench.domain.qualifiers import QualifierSet
from genome_workbench.ui.main_window import MainWindow

pytestmark = pytest.mark.ui

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


def _open_circular_project(window: MainWindow, tmp_path: Path, monkeypatch):
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

    fixture_path = str(FIXTURES_DIR / "circular_origin.gbk")
    monkeypatch.setattr(
        "genome_workbench.ui.main_window.QFileDialog.getOpenFileName",
        staticmethod(lambda *a, **k: (fixture_path, "")),
    )
    window._on_import_genbank()
    record = window.project_service.list_records()[0]
    window._on_record_selected(record.id)
    return record


def _wheel_event(pos: QPointF, angle_delta_y: int) -> QWheelEvent:
    return QWheelEvent(
        pos,
        pos,
        QPoint(0, 0),
        QPoint(0, angle_delta_y),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )


def test_wheel_zooms_in_and_out_on_circular_map(qtbot, tmp_path, monkeypatch):
    window = MainWindow(blast_work_dir=tmp_path / "blast_work")
    window.resize(900, 700)
    qtbot.addWidget(window)
    with qtbot.waitExposed(window):
        window.show()
    _open_circular_project(window, tmp_path, monkeypatch)

    canvas = window.circular_canvas
    assert canvas.viewport_transform.zoom_scale == 1.0

    center = QPointF(canvas.width() / 2, canvas.height() / 2)
    canvas.wheelEvent(_wheel_event(center, 120))
    assert canvas.viewport_transform.zoom_scale > 1.0

    zoomed_scale = canvas.viewport_transform.zoom_scale
    canvas.wheelEvent(_wheel_event(center, -120))
    assert canvas.viewport_transform.zoom_scale < zoomed_scale


def test_drag_on_empty_background_rotates_the_ring(qtbot, tmp_path, monkeypatch):
    window = MainWindow(blast_work_dir=tmp_path / "blast_work")
    window.resize(900, 700)
    qtbot.addWidget(window)
    with qtbot.waitExposed(window):
        window.show()
    _open_circular_project(window, tmp_path, monkeypatch)

    canvas = window.circular_canvas
    assert canvas.viewport_transform.rotation_degrees == 0.0

    # drag from directly above center to directly right of center: empty
    # background at both points (the only feature is a thin arc), so this
    # should rotate rather than select/deselect anything.
    cx, cy = canvas.width() / 2, canvas.height() / 2
    start = QPoint(int(cx), int(cy - 60))
    end = QPoint(int(cx + 60), int(cy))

    qtbot.mousePress(canvas, Qt.MouseButton.LeftButton, pos=start)
    qtbot.mouseMove(canvas, pos=end)
    qtbot.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=end)

    assert canvas.viewport_transform.rotation_degrees != 0.0


def test_shift_drag_on_empty_background_pans_the_ring(qtbot, tmp_path, monkeypatch):
    window = MainWindow(blast_work_dir=tmp_path / "blast_work")
    window.resize(900, 700)
    qtbot.addWidget(window)
    with qtbot.waitExposed(window):
        window.show()
    _open_circular_project(window, tmp_path, monkeypatch)

    canvas = window.circular_canvas
    assert canvas.viewport_transform.pan_x == 0.0
    assert canvas.viewport_transform.pan_y == 0.0
    assert canvas.viewport_transform.rotation_degrees == 0.0

    cx, cy = canvas.width() / 2, canvas.height() / 2
    start = QPoint(int(cx), int(cy - 60))
    end = QPoint(int(cx + 40), int(cy - 20))

    QTest.mousePress(canvas, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.ShiftModifier, start)
    qtbot.mouseMove(canvas, pos=end)
    QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.ShiftModifier, end)

    # Shift+drag pans (translates the ring center), not rotates.
    assert canvas.viewport_transform.pan_x != 0.0 or canvas.viewport_transform.pan_y != 0.0
    assert canvas.viewport_transform.rotation_degrees == 0.0


def test_clicking_a_feature_still_selects_instead_of_rotating(qtbot, tmp_path, monkeypatch):
    window = MainWindow(blast_work_dir=tmp_path / "blast_work")
    window.resize(900, 700)
    qtbot.addWidget(window)
    with qtbot.waitExposed(window):
        window.show()
    record = _open_circular_project(window, tmp_path, monkeypatch)

    feature = window.annotation_service.create_simple_feature(
        record, 1, record.length, 1, "misc_feature", QualifierSet.from_pairs([("note", "whole")])
    )
    window._refresh_features_only()

    canvas = window.circular_canvas
    # a feature spanning the whole record covers the entire ring at radius - RING_WIDTH-GAP
    center, radius = canvas._center_and_radius()
    from genome_workbench.ui.views.circular_genome_canvas import _RING_GAP, _RING_WIDTH

    click_point = QPoint(int(center.x()), int(center.y() - (radius - _RING_WIDTH - _RING_GAP)))

    qtbot.mousePress(canvas, Qt.MouseButton.LeftButton, pos=click_point)
    qtbot.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=click_point)

    assert canvas._selected_feature_id == feature.id
    assert canvas.viewport_transform.rotation_degrees == 0.0


def test_reset_view_restores_default_zoom_and_rotation(qtbot, tmp_path, monkeypatch):
    window = MainWindow(blast_work_dir=tmp_path / "blast_work")
    qtbot.addWidget(window)
    _open_circular_project(window, tmp_path, monkeypatch)

    canvas = window.circular_canvas
    canvas.wheelEvent(_wheel_event(QPointF(canvas.width() / 2, canvas.height() / 2), 120))
    canvas._transform = canvas._transform.rotated(45.0)
    assert not canvas.viewport_transform.is_at_default

    canvas.reset_view()

    assert canvas.viewport_transform.is_at_default


def test_switching_records_resets_the_view(qtbot, tmp_path, monkeypatch):
    window = MainWindow(blast_work_dir=tmp_path / "blast_work")
    qtbot.addWidget(window)
    record = _open_circular_project(window, tmp_path, monkeypatch)

    canvas = window.circular_canvas
    canvas.wheelEvent(_wheel_event(QPointF(canvas.width() / 2, canvas.height() / 2), 120))
    assert canvas.viewport_transform.zoom_scale > 1.0

    window._on_record_selected(record.id)  # re-select the same (only) record

    assert canvas.viewport_transform.is_at_default
