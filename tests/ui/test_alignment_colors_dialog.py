"""Per-residue color customization for the Alignment View -- same shape as
test_feature_colors_dialog.py, since AlignmentColorsDialog mirrors
FeatureColorsDialog's structure.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtGui import QColor

from genome_workbench.domain.models import MoleculeType
from genome_workbench.ui.dialogs.alignment_colors_dialog import AlignmentColorsDialog
from genome_workbench.ui.rendering.nucleotide_colors import (
    DEFAULT_AMINO_ACID_COLORS,
    DEFAULT_NUCLEOTIDE_COLORS,
)

pytestmark = pytest.mark.ui


def test_default_nucleotides_are_listed_with_default_colors(qtbot):
    dialog = AlignmentColorsDialog({}, MoleculeType.DNA)
    qtbot.addWidget(dialog)
    assert dialog._table.rowCount() == len(DEFAULT_NUCLEOTIDE_COLORS)


def test_protein_molecule_type_uses_amino_acid_palette(qtbot):
    dialog = AlignmentColorsDialog({}, MoleculeType.PROTEIN)
    qtbot.addWidget(dialog)
    assert dialog._table.rowCount() == len(DEFAULT_AMINO_ACID_COLORS)
    types = {dialog._table.item(r, 0).text() for r in range(dialog._table.rowCount())}
    assert "D" in types  # aspartate, not a nucleotide code


def test_existing_overrides_are_reflected_in_swatches(qtbot):
    dialog = AlignmentColorsDialog({"A": "#ff00ff"}, MoleculeType.DNA)
    qtbot.addWidget(dialog)
    row = next(r for r in range(dialog._table.rowCount()) if dialog._table.item(r, 0).text() == "A")
    swatch = dialog._table.cellWidget(row, 1)
    assert swatch.text() == "#ff00ff"


def test_extra_residues_get_their_own_row(qtbot):
    dialog = AlignmentColorsDialog({}, MoleculeType.DNA, extra_residues=["R"])
    qtbot.addWidget(dialog)
    types = {dialog._table.item(r, 0).text() for r in range(dialog._table.rowCount())}
    assert "R" in types


def test_picking_a_color_updates_overrides(qtbot, monkeypatch):
    dialog = AlignmentColorsDialog({}, MoleculeType.DNA)
    qtbot.addWidget(dialog)
    monkeypatch.setattr(
        "genome_workbench.ui.dialogs.alignment_colors_dialog.QColorDialog.getColor",
        staticmethod(lambda *a, **k: QColor("#00ff00")),
    )
    row = next(r for r in range(dialog._table.rowCount()) if dialog._table.item(r, 0).text() == "A")

    dialog._on_pick_color(row)

    assert dialog.overrides["A"] == "#00ff00"
    swatch = dialog._table.cellWidget(row, 1)
    assert swatch.text() == "#00ff00"


def test_reset_row_removes_override(qtbot):
    dialog = AlignmentColorsDialog({"A": "#ff00ff"}, MoleculeType.DNA)
    qtbot.addWidget(dialog)
    row = next(r for r in range(dialog._table.rowCount()) if dialog._table.item(r, 0).text() == "A")

    dialog._on_reset_row(row)

    assert "A" not in dialog.overrides
    swatch = dialog._table.cellWidget(row, 1)
    assert swatch.text() == DEFAULT_NUCLEOTIDE_COLORS["A"]


def test_reset_all_clears_every_override(qtbot):
    dialog = AlignmentColorsDialog({"A": "#ff00ff", "C": "#00ffff"}, MoleculeType.DNA)
    qtbot.addWidget(dialog)

    dialog._on_reset_all()

    assert dialog.overrides == {}


def test_add_residue_creates_a_new_row(qtbot, monkeypatch):
    dialog = AlignmentColorsDialog({}, MoleculeType.DNA)
    qtbot.addWidget(dialog)
    before = dialog._table.rowCount()
    monkeypatch.setattr(
        "genome_workbench.ui.dialogs.alignment_colors_dialog.QInputDialog.getText",
        staticmethod(lambda *a, **k: ("R", True)),
    )

    dialog._on_add_residue()

    assert dialog._table.rowCount() == before + 1
    types = {dialog._table.item(r, 0).text() for r in range(dialog._table.rowCount())}
    assert "R" in types


def test_main_window_alignment_colors_dialog_persists_and_applies(
    qtbot, tmp_path: Path, monkeypatch
):
    from genome_workbench.domain.models import Alignment, AlignmentSequence
    from genome_workbench.ui.main_window import MainWindow
    from genome_workbench.ui.rendering.nucleotide_colors import load_color_overrides

    window = MainWindow(
        blast_work_dir=tmp_path / "blast_work",
        alignment_color_overrides_dir=tmp_path / "alignment_colors",
    )
    qtbot.addWidget(window)
    window.project_service.create_new(tmp_path / "proj.gwbproj", "Alignment Colors Test")
    alignment = Alignment(name="msa1", molecule_type=MoleculeType.DNA, length=4)
    window.project_service.save_alignment(
        alignment, [AlignmentSequence(alignment_id=alignment.id, label="s1", sequence="ACGT")]
    )
    window._on_alignment_selected(alignment.id)

    def fake_exec(self):
        self.overrides["A"] = "#ff00ff"
        return 1

    monkeypatch.setattr(AlignmentColorsDialog, "exec", fake_exec)
    window._on_alignment_colors_requested()

    assert window._alignment_color_overrides["nucleotide"]["A"] == "#ff00ff"
    assert window.alignment_view_page.canvas._color_overrides["A"] == "#ff00ff"
    persisted = load_color_overrides(tmp_path / "alignment_colors")
    assert persisted["nucleotide"]["A"] == "#ff00ff"
