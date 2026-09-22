"""Horizontal scrollbar on the Alignment View -- same user-reported gap as
the Genome Map's: zoom in/out existed but there was no visible, discoverable
way to pan sideways across columns (only Shift+wheel). The vertical
scrollbar for rows already existed; this adds the missing horizontal one
for columns.
"""

from __future__ import annotations

import pytest

from genome_workbench.domain.models import Alignment, AlignmentSequence, MoleculeType
from genome_workbench.ui.views.alignment_view_page import AlignmentViewPage

pytestmark = pytest.mark.ui


def _alignment_with_sequence(length: int = 1000) -> tuple[Alignment, list[AlignmentSequence]]:
    alignment = Alignment(name="msa1", molecule_type=MoleculeType.DNA, length=length)
    sequences = [
        AlignmentSequence(alignment_id=alignment.id, label="seq1", sequence="A" * length),
        AlignmentSequence(alignment_id=alignment.id, label="seq2", sequence="A" * length),
    ]
    return alignment, sequences


def test_column_scrollbar_disabled_with_no_alignment(qtbot):
    page = AlignmentViewPage()
    qtbot.addWidget(page)
    assert not page._column_scrollbar.isEnabled()


def test_column_scrollbar_enabled_and_ranged_after_zooming_in(qtbot):
    page = AlignmentViewPage()
    qtbot.addWidget(page)
    page.resize(800, 400)
    alignment, sequences = _alignment_with_sequence()
    page.set_alignment(alignment, sequences)

    # whole alignment fits in view -- nothing to scroll yet
    assert not page._column_scrollbar.isEnabled()

    page.canvas.set_viewport(0, 100)  # zoom in

    assert page._column_scrollbar.isEnabled()
    assert page._column_scrollbar.maximum() == 1000 - 100
    assert page._column_scrollbar.pageStep() == 100
    assert page._column_scrollbar.value() == 0


def test_moving_column_scrollbar_pans_the_canvas(qtbot):
    page = AlignmentViewPage()
    qtbot.addWidget(page)
    page.resize(800, 400)
    alignment, sequences = _alignment_with_sequence()
    page.set_alignment(alignment, sequences)
    page.canvas.set_viewport(0, 100)

    page._column_scrollbar.setValue(400)

    vt = page.canvas.viewport_transform
    assert vt.view_start0 == 400
    assert vt.view_end0 == 500


def test_panning_the_canvas_updates_the_column_scrollbar_thumb(qtbot):
    page = AlignmentViewPage()
    qtbot.addWidget(page)
    page.resize(800, 400)
    alignment, sequences = _alignment_with_sequence()
    page.set_alignment(alignment, sequences)
    page.canvas.set_viewport(0, 100)

    page.canvas.set_viewport(600, 700)  # e.g. from a wheel-pan

    assert page._column_scrollbar.value() == 600


def test_fitting_whole_alignment_disables_the_column_scrollbar_again(qtbot):
    page = AlignmentViewPage()
    qtbot.addWidget(page)
    page.resize(800, 400)
    alignment, sequences = _alignment_with_sequence()
    page.set_alignment(alignment, sequences)
    page.canvas.set_viewport(0, 100)
    assert page._column_scrollbar.isEnabled()

    page._on_fit()

    assert not page._column_scrollbar.isEnabled()
