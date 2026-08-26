"""Dark-theme readability for the genome canvases (KNOWN_LIMITATIONS.md gap:
DPI/theme unverified). GenomeCanvas and CircularGenomeCanvas fill their
background with `palette().base()` so it follows the app theme, but several
foreground colors used to be hardcoded near-black hex values -- readable on
the default light palette, nearly invisible against a dark one. Foreground
colors now derive from the palette (`Text`/`PlaceholderText`/`Highlight`) so
contrast holds under both themes.
"""

from __future__ import annotations

import pytest
from PySide6.QtGui import QColor, QPalette

from genome_workbench.domain.models import MoleculeType, SequenceRecord, Topology
from genome_workbench.ui.views.circular_genome_canvas import CircularGenomeCanvas
from genome_workbench.ui.views.genome_canvas import GenomeCanvas

pytestmark = pytest.mark.ui


def _dark_palette() -> QPalette:
    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window, QColor(53, 53, 53))
    pal.setColor(QPalette.ColorRole.WindowText, QColor(220, 220, 220))
    pal.setColor(QPalette.ColorRole.Base, QColor(35, 35, 35))
    pal.setColor(QPalette.ColorRole.Text, QColor(220, 220, 220))
    pal.setColor(QPalette.ColorRole.PlaceholderText, QColor(150, 150, 150))
    pal.setColor(QPalette.ColorRole.Highlight, QColor(64, 128, 200))
    return pal


def _contrast_ratio(c1: QColor, c2: QColor) -> float:
    def rel_luminance(c: QColor) -> float:
        def channel(v: int) -> float:
            v_norm = v / 255
            return v_norm / 12.92 if v_norm <= 0.03928 else ((v_norm + 0.055) / 1.055) ** 2.4

        r, g, b = channel(c.red()), channel(c.green()), channel(c.blue())
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    l1, l2 = rel_luminance(c1) + 0.05, rel_luminance(c2) + 0.05
    return max(l1, l2) / min(l1, l2)


def _sample_record() -> SequenceRecord:
    return SequenceRecord(
        display_id="theme_check",
        name="theme_check",
        description="",
        molecule_type=MoleculeType.DNA,
        topology=Topology.CIRCULAR,
        sequence="ACGT" * 500,
        checksum_sha256="",
        source_format="synthetic",
    )


def test_genome_canvas_text_contrasts_against_dark_palette(qtbot):
    canvas = GenomeCanvas()
    qtbot.addWidget(canvas)
    canvas.setPalette(_dark_palette())
    canvas.set_record(_sample_record(), [])
    canvas.set_viewport(0, 200)  # base-level LOD, exercises text rendering

    base = canvas.palette().color(QPalette.ColorRole.Base)
    assert _contrast_ratio(base, canvas._fg_color()) >= 4.5
    assert _contrast_ratio(base, canvas._muted_color()) >= 3.0


def test_genome_canvas_text_contrasts_against_light_palette(qtbot):
    canvas = GenomeCanvas()
    qtbot.addWidget(canvas)
    canvas.set_record(_sample_record(), [])
    canvas.set_viewport(0, 200)

    base = canvas.palette().color(QPalette.ColorRole.Base)
    assert _contrast_ratio(base, canvas._fg_color()) >= 4.5


def test_circular_genome_canvas_text_contrasts_against_dark_palette(qtbot):
    canvas = CircularGenomeCanvas()
    qtbot.addWidget(canvas)
    canvas.setPalette(_dark_palette())
    canvas.set_record(_sample_record(), [])

    base = canvas.palette().color(QPalette.ColorRole.Base)
    assert _contrast_ratio(base, canvas._fg_color()) >= 4.5


def test_canvases_render_without_error_under_dark_palette(qtbot):
    """Regression guard: paintEvent must not raise when the palette changes,
    covering the render path that previously used fixed hex colors."""
    canvas = GenomeCanvas()
    qtbot.addWidget(canvas)
    canvas.setPalette(_dark_palette())
    canvas.set_record(_sample_record(), [])
    canvas.set_viewport(0, 200)
    canvas.resize(600, 400)
    canvas.repaint()

    circular = CircularGenomeCanvas()
    qtbot.addWidget(circular)
    circular.setPalette(_dark_palette())
    circular.set_record(_sample_record(), [])
    circular.resize(400, 400)
    circular.repaint()
