"""Feature-type color customization -- previously the palette was a fixed
built-in dict with no UI to change it (user-reported gap)."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtGui import QColor

from genome_workbench.ui.dialogs.feature_colors_dialog import FeatureColorsDialog
from genome_workbench.ui.rendering.feature_colors import DEFAULT_FEATURE_COLORS

pytestmark = pytest.mark.ui


def test_default_types_are_listed_with_default_colors(qtbot):
    dialog = FeatureColorsDialog({})
    qtbot.addWidget(dialog)
    assert dialog._table.rowCount() == len(DEFAULT_FEATURE_COLORS)


def test_existing_overrides_are_reflected_in_swatches(qtbot):
    dialog = FeatureColorsDialog({"CDS": "#ff00ff"})
    qtbot.addWidget(dialog)
    row = next(
        r for r in range(dialog._table.rowCount()) if dialog._table.item(r, 0).text() == "CDS"
    )
    swatch = dialog._table.cellWidget(row, 1)
    assert swatch.text() == "#ff00ff"


def test_extra_types_get_their_own_row(qtbot):
    dialog = FeatureColorsDialog({}, extra_types=["ncRNA"])
    qtbot.addWidget(dialog)
    types = {dialog._table.item(r, 0).text() for r in range(dialog._table.rowCount())}
    assert "ncRNA" in types


def test_picking_a_color_updates_overrides(qtbot, monkeypatch):
    dialog = FeatureColorsDialog({})
    qtbot.addWidget(dialog)
    monkeypatch.setattr(
        "genome_workbench.ui.dialogs.feature_colors_dialog.QColorDialog.getColor",
        staticmethod(lambda *a, **k: QColor("#00ff00")),
    )
    row = next(
        r for r in range(dialog._table.rowCount()) if dialog._table.item(r, 0).text() == "CDS"
    )

    dialog._on_pick_color(row)

    assert dialog.overrides["CDS"] == "#00ff00"
    swatch = dialog._table.cellWidget(row, 1)
    assert swatch.text() == "#00ff00"


def test_picking_an_invalid_color_does_not_change_overrides(qtbot, monkeypatch):
    dialog = FeatureColorsDialog({})
    qtbot.addWidget(dialog)
    monkeypatch.setattr(
        "genome_workbench.ui.dialogs.feature_colors_dialog.QColorDialog.getColor",
        staticmethod(lambda *a, **k: QColor()),  # invalid/cancelled
    )
    row = next(
        r for r in range(dialog._table.rowCount()) if dialog._table.item(r, 0).text() == "CDS"
    )

    dialog._on_pick_color(row)

    assert "CDS" not in dialog.overrides


def test_reset_row_removes_override(qtbot):
    dialog = FeatureColorsDialog({"CDS": "#ff00ff"})
    qtbot.addWidget(dialog)
    row = next(
        r for r in range(dialog._table.rowCount()) if dialog._table.item(r, 0).text() == "CDS"
    )

    dialog._on_reset_row(row)

    assert "CDS" not in dialog.overrides
    swatch = dialog._table.cellWidget(row, 1)
    assert swatch.text() == DEFAULT_FEATURE_COLORS["CDS"]


def test_reset_all_clears_every_override(qtbot):
    dialog = FeatureColorsDialog({"CDS": "#ff00ff", "gene": "#00ffff"})
    qtbot.addWidget(dialog)

    dialog._on_reset_all()

    assert dialog.overrides == {}


def test_add_type_creates_a_new_row(qtbot, monkeypatch):
    dialog = FeatureColorsDialog({})
    qtbot.addWidget(dialog)
    before = dialog._table.rowCount()
    monkeypatch.setattr(
        "genome_workbench.ui.dialogs.feature_colors_dialog.QInputDialog.getText",
        staticmethod(lambda *a, **k: ("terminator", True)),
    )

    dialog._on_add_type()

    assert dialog._table.rowCount() == before + 1
    types = {dialog._table.item(r, 0).text() for r in range(dialog._table.rowCount())}
    assert "terminator" in types


def test_add_duplicate_type_does_not_create_a_second_row(qtbot, monkeypatch):
    dialog = FeatureColorsDialog({})
    qtbot.addWidget(dialog)
    before = dialog._table.rowCount()
    monkeypatch.setattr(
        "genome_workbench.ui.dialogs.feature_colors_dialog.QInputDialog.getText",
        staticmethod(lambda *a, **k: ("CDS", True)),
    )

    dialog._on_add_type()

    assert dialog._table.rowCount() == before


def test_main_window_feature_colors_dialog_persists_and_applies(qtbot, tmp_path: Path, monkeypatch):
    from genome_workbench.ui.main_window import MainWindow
    from genome_workbench.ui.rendering.feature_colors import load_color_overrides

    window = MainWindow(
        blast_work_dir=tmp_path / "blast_work", color_overrides_dir=tmp_path / "colors"
    )
    qtbot.addWidget(window)

    def fake_exec(self):
        self.overrides["CDS"] = "#ff00ff"
        return 1

    monkeypatch.setattr(FeatureColorsDialog, "exec", fake_exec)
    window._on_feature_colors_requested()

    assert window._color_overrides["CDS"] == "#ff00ff"
    assert window.genome_map_page.canvas._color_overrides["CDS"] == "#ff00ff"
    assert window.circular_canvas._color_overrides["CDS"] == "#ff00ff"
    assert load_color_overrides(tmp_path / "colors")["CDS"] == "#ff00ff"
