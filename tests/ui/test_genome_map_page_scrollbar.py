"""Horizontal scrollbar on the Genome Map -- user-reported gap: zoom in/out
existed but there was no visible way to pan sideways along the sequence
without knowing about Shift+wheel. The minimap could already jump around,
but a standard scrollbar is the familiar, discoverable control for it.
"""

from __future__ import annotations

import pytest

from genome_workbench.domain.models import MoleculeType, SequenceRecord, Topology
from genome_workbench.ui.views.genome_map_page import GenomeMapPage

pytestmark = pytest.mark.ui


def _record(length: int = 10_000) -> SequenceRecord:
    return SequenceRecord(
        display_id="rec1",
        sequence="A" * length,
        checksum_sha256="x",
        molecule_type=MoleculeType.DNA,
        topology=Topology.LINEAR,
    )


def test_scrollbar_disabled_with_no_record(qtbot):
    page = GenomeMapPage()
    qtbot.addWidget(page)
    assert not page._position_scrollbar.isEnabled()


def test_scrollbar_enabled_and_ranged_after_zooming_in(qtbot):
    page = GenomeMapPage()
    qtbot.addWidget(page)
    page.resize(800, 400)
    page.set_record(_record(), [])

    # whole genome fits in view -- nothing to scroll yet
    assert not page._position_scrollbar.isEnabled()

    page.canvas.set_viewport(0, 500)  # zoom in: now less than the whole genome is visible

    assert page._position_scrollbar.isEnabled()
    assert page._position_scrollbar.maximum() == 10_000 - 500
    assert page._position_scrollbar.pageStep() == 500
    assert page._position_scrollbar.value() == 0


def test_moving_scrollbar_pans_the_canvas(qtbot):
    page = GenomeMapPage()
    qtbot.addWidget(page)
    page.resize(800, 400)
    page.set_record(_record(), [])
    page.canvas.set_viewport(0, 500)

    page._position_scrollbar.setValue(2000)

    vt = page.canvas.viewport_transform
    assert vt.view_start0 == 2000
    assert vt.view_end0 == 2500


def test_panning_the_canvas_updates_the_scrollbar_thumb(qtbot):
    page = GenomeMapPage()
    qtbot.addWidget(page)
    page.resize(800, 400)
    page.set_record(_record(), [])
    page.canvas.set_viewport(0, 500)

    page.canvas.set_viewport(3000, 3500)  # e.g. from a wheel-pan or minimap click

    assert page._position_scrollbar.value() == 3000


def test_zooming_out_to_whole_genome_disables_the_scrollbar_again(qtbot):
    page = GenomeMapPage()
    qtbot.addWidget(page)
    page.resize(800, 400)
    page.set_record(_record(), [])
    page.canvas.set_viewport(0, 500)
    assert page._position_scrollbar.isEnabled()

    page.canvas.zoom_to_whole_genome()

    assert not page._position_scrollbar.isEnabled()
