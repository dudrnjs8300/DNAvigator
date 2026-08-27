"""Ctrl+C copy support on GenomeCanvas, CircularGenomeCanvas, and
FeatureTableView -- previously there was no way to copy a sequence
selection or feature-table rows without switching to another app to
retype them (user-reported gap).
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

from genome_workbench.domain.locations import LocationPart
from genome_workbench.domain.models import Feature, MoleculeType, SequenceRecord, Topology
from genome_workbench.domain.qualifiers import QualifierSet
from genome_workbench.ui.views.circular_genome_canvas import CircularGenomeCanvas
from genome_workbench.ui.views.feature_table_view import FeatureTableView
from genome_workbench.ui.views.genome_canvas import GenomeCanvas

pytestmark = pytest.mark.ui


def _copy_key_event() -> QKeyEvent:
    return QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier, "c")


def _record() -> SequenceRecord:
    return SequenceRecord(
        display_id="copy_test",
        sequence="ACGTACGTACGTACGTACGTACGTACGTACGTACGTACGT",
        checksum_sha256="x",
        molecule_type=MoleculeType.DNA,
        topology=Topology.LINEAR,
    )


def _feature(start0: int, end0: int, strand: int = 1) -> Feature:
    return Feature(
        type="CDS",
        strand=strand,
        parts=[LocationPart(start0=start0, end0=end0, order_index=0)],
        qualifiers=QualifierSet.from_pairs([("gene", "testGene")]),
    )


def test_genome_canvas_copies_range_selection(qtbot):
    canvas = GenomeCanvas()
    qtbot.addWidget(canvas)
    record = _record()
    canvas.set_record(record, [])
    canvas.set_viewport(0, 40)
    canvas._selection = (5, 15)

    canvas.keyPressEvent(_copy_key_event())

    assert QApplication.clipboard().text() == record.sequence[5:15]


def test_genome_canvas_copies_selected_feature_sequence(qtbot):
    canvas = GenomeCanvas()
    qtbot.addWidget(canvas)
    record = _record()
    feature = _feature(0, 10)
    canvas.set_record(record, [feature])
    canvas.set_viewport(0, 40)
    canvas.select_feature(feature.id)

    canvas.keyPressEvent(_copy_key_event())

    assert QApplication.clipboard().text() == record.sequence[0:10]


def test_genome_canvas_copies_reverse_strand_feature_as_reverse_complement(qtbot):
    from genome_workbench.domain.sequence_ops import reverse_complement

    canvas = GenomeCanvas()
    qtbot.addWidget(canvas)
    record = _record()
    feature = _feature(0, 10, strand=-1)
    canvas.set_record(record, [feature])
    canvas.set_viewport(0, 40)
    canvas.select_feature(feature.id)

    canvas.keyPressEvent(_copy_key_event())

    assert QApplication.clipboard().text() == reverse_complement(record.sequence[0:10])


def test_genome_canvas_copy_with_nothing_selected_does_not_crash(qtbot):
    canvas = GenomeCanvas()
    qtbot.addWidget(canvas)
    canvas.set_record(_record(), [])
    canvas.set_viewport(0, 40)

    canvas.keyPressEvent(_copy_key_event())  # should not raise


def test_circular_canvas_copies_selected_feature_sequence(qtbot):
    canvas = CircularGenomeCanvas()
    qtbot.addWidget(canvas)
    record = _record()
    feature = _feature(0, 10)
    canvas.set_record(record, [feature])
    canvas.select_feature(feature.id)

    canvas.keyPressEvent(_copy_key_event())

    assert QApplication.clipboard().text() == record.sequence[0:10]


def test_feature_table_copies_selected_rows_as_tsv(qtbot):
    table = FeatureTableView()
    qtbot.addWidget(table)
    features = [_feature(0, 10), _feature(20, 30, strand=-1)]
    table.set_features(features)
    table.selectAll()

    table.keyPressEvent(_copy_key_event())

    copied = QApplication.clipboard().text()
    lines = copied.splitlines()
    assert lines[0] == "Label\tType\tStart\tEnd\tStrand\tLength\tGene\tProduct"
    assert len(lines) == 3  # header + 2 rows
    assert "CDS" in lines[1] and "CDS" in lines[2]


def test_feature_table_copy_with_no_selection_does_not_crash(qtbot):
    table = FeatureTableView()
    qtbot.addWidget(table)
    table.set_features([_feature(0, 10)])

    table.keyPressEvent(_copy_key_event())  # nothing selected -- should not raise
