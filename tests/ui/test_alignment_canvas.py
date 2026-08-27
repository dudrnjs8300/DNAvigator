import pytest
from PySide6.QtCore import Qt

from genome_workbench.domain.models import Alignment, AlignmentSequence, MoleculeType
from genome_workbench.ui.views.alignment_canvas import AlignmentCanvas

pytestmark = pytest.mark.ui


def _alignment_with_rows(n_rows: int = 3, length: int = 10) -> tuple[Alignment, list]:
    alignment = Alignment(name="test", molecule_type=MoleculeType.DNA, length=length)
    sequences = [
        AlignmentSequence(
            alignment_id=alignment.id,
            label=f"seq{i}",
            sequence=("ATG-CCGTAA" * ((length // 10) + 1))[:length],
            order_index=i,
        )
        for i in range(n_rows)
    ]
    return alignment, sequences


def test_no_alignment_loaded_does_not_crash_paint(qtbot):
    canvas = AlignmentCanvas()
    qtbot.addWidget(canvas)
    canvas.resize(400, 200)
    canvas.show()
    canvas.grab()  # must not raise
    assert canvas.viewport_transform is None


def test_set_alignment_initializes_whole_alignment_viewport(qtbot):
    canvas = AlignmentCanvas()
    qtbot.addWidget(canvas)
    canvas.resize(800, 300)
    alignment, sequences = _alignment_with_rows()
    canvas.set_alignment(alignment, sequences)
    vt = canvas.viewport_transform
    assert vt is not None
    assert vt.view_start0 == 0
    assert vt.view_end0 == alignment.length
    canvas.show()
    canvas.grab()


def test_zoom_and_pan_do_not_crash_at_any_lod(qtbot):
    canvas = AlignmentCanvas()
    qtbot.addWidget(canvas)
    canvas.resize(800, 300)
    alignment, sequences = _alignment_with_rows(length=200)
    canvas.set_alignment(alignment, sequences)
    canvas.show()

    canvas.set_viewport(0, 200)  # zoomed out -- conservation bar / no cells
    canvas.grab()
    canvas.set_viewport(0, 40)  # medium -- colored blocks, no letters
    canvas.grab()
    canvas.set_viewport(0, 5)  # zoomed in -- colored blocks + letters
    canvas.grab()


def test_total_and_visible_row_counts(qtbot):
    canvas = AlignmentCanvas()
    qtbot.addWidget(canvas)
    canvas.resize(800, 300)
    alignment, sequences = _alignment_with_rows(n_rows=50)
    canvas.set_alignment(alignment, sequences)
    assert canvas.total_row_count == 50
    assert 0 < canvas.visible_row_count < 50


def test_set_first_visible_row_is_clamped(qtbot):
    canvas = AlignmentCanvas()
    qtbot.addWidget(canvas)
    canvas.resize(800, 300)
    alignment, sequences = _alignment_with_rows(n_rows=10)
    canvas.set_alignment(alignment, sequences)

    canvas.set_first_visible_row(-5)
    assert canvas.first_visible_row == 0

    canvas.set_first_visible_row(1000)
    assert canvas.first_visible_row == 9


def test_set_alignment_none_clears_state(qtbot):
    canvas = AlignmentCanvas()
    qtbot.addWidget(canvas)
    alignment, sequences = _alignment_with_rows()
    canvas.set_alignment(alignment, sequences)
    canvas.set_alignment(None, [])
    assert canvas.viewport_transform is None
    assert canvas.total_row_count == 0
    canvas.grab()  # "No alignment loaded" path must not crash


def test_column_clicked_emits_signal(qtbot):
    canvas = AlignmentCanvas()
    qtbot.addWidget(canvas)
    canvas.resize(800, 300)
    alignment, sequences = _alignment_with_rows(length=20)
    canvas.set_alignment(alignment, sequences)
    canvas.show()

    with qtbot.waitSignal(canvas.columnClicked, timeout=1000) as blocker:
        qtbot.mouseClick(canvas, Qt.MouseButton.LeftButton, pos=canvas.rect().center())
    assert isinstance(blocker.args[0], int)
