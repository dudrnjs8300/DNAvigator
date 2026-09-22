"""Ctrl+F for the Alignment View -- searches sequence motifs (against each
row's own ungapped bases) and sequence names/labels in one box, since
"find a sequence" was ambiguous between the two (user-reported request).
"""

from __future__ import annotations

import pytest

from genome_workbench.domain.models import AlignmentSequence
from genome_workbench.ui.dialogs.find_in_alignment_dialog import FindInAlignmentDialog

pytestmark = pytest.mark.ui


def _sequences() -> list[AlignmentSequence]:
    return [
        AlignmentSequence(alignment_id="a1", label="isolate_KR01", sequence="ATG--CCGTAA"),
        AlignmentSequence(alignment_id="a1", label="isolate_US14", sequence="ATGACCGTAAG"),
        AlignmentSequence(alignment_id="a1", label="reference_NCTC", sequence="ATGACCATAAG"),
    ]


def test_empty_query_shows_no_results(qtbot):
    dialog = FindInAlignmentDialog(_sequences())
    qtbot.addWidget(dialog)
    dialog._run_search("")
    assert dialog._results.rowCount() == 0


def test_motif_search_matches_across_a_gap_padded_by_another_row(qtbot):
    dialog = FindInAlignmentDialog(_sequences())
    qtbot.addWidget(dialog)

    # "GCC" is contiguous in isolate_KR01's own ungapped bases (ATGCCGTAA)
    # even though its aligned text has a gap right before it (ATG--CCGTAA)
    dialog._run_search("GCC")

    rows = [dialog._results.item(r, 0).text() for r in range(dialog._results.rowCount())]
    assert "isolate_KR01" in rows


def test_motif_search_is_case_insensitive(qtbot):
    dialog = FindInAlignmentDialog(_sequences())
    qtbot.addWidget(dialog)
    dialog._run_search("gcc")
    assert dialog._results.rowCount() > 0


def test_motif_search_finds_matches_in_every_matching_row(qtbot):
    dialog = FindInAlignmentDialog(_sequences())
    qtbot.addWidget(dialog)
    dialog._run_search("ATGACC")  # present in isolate_US14 and reference_NCTC
    rows = {dialog._results.item(r, 0).text() for r in range(dialog._results.rowCount())}
    assert rows == {"isolate_US14", "reference_NCTC"}


def test_label_search_matches_by_sequence_name(qtbot):
    dialog = FindInAlignmentDialog(_sequences())
    qtbot.addWidget(dialog)
    dialog._run_search("KR01")
    assert dialog._results.rowCount() == 1
    assert dialog._results.item(0, 1).text() == "name"


def test_activating_a_result_emits_result_chosen_with_column_range(qtbot):
    sequences = _sequences()
    dialog = FindInAlignmentDialog(sequences)
    qtbot.addWidget(dialog)
    dialog._run_search("ATGACC")

    with qtbot.waitSignal(dialog.resultChosen, timeout=1000) as blocker:
        dialog._activate_row(0)
    seq_id, col_start, col_end = blocker.args
    assert seq_id in {s.id for s in sequences}
    assert col_end > col_start


def test_no_match_reports_zero_results(qtbot):
    dialog = FindInAlignmentDialog(_sequences())
    qtbot.addWidget(dialog)
    dialog._run_search("ZZZZZZ")
    assert dialog._results.rowCount() == 0
    assert "0 match" in dialog._status_label.text()
