"""Minimal base-level sequence view.

P0/Phase 1 implementation: a read-only wrapped text display with a 1-based
coordinate gutter, sufficient for the vertical slice (bacterial-scale
fixtures). A fully custom-painted, viewport-virtualized renderer with LOD is
Phase 3 work (see docs/KNOWN_LIMITATIONS.md) — QPlainTextEdit already does
its own internal line virtualization, so this remains usable well beyond
toy-sized inputs, but it does not yet render feature highlight tracks or
support base-level click selection mapped back to genomic coordinates.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QPlainTextEdit, QVBoxLayout, QWidget

from genome_workbench.domain.models import SequenceRecord

_LINE_WIDTH = 60


class SequenceView(QWidget):
    selectionChanged1Based = Signal(int, int)  # start, end (1-based inclusive), 0 if empty

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._record: SequenceRecord | None = None

        self._text_edit = QPlainTextEdit(self)
        self._text_edit.setReadOnly(True)
        self._text_edit.setFont(QFont("Consolas", 10))
        self._text_edit.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._text_edit)

    def set_record(self, record: SequenceRecord | None) -> None:
        self._record = record
        if record is None:
            self._text_edit.setPlainText("")
            return
        lines = []
        seq = record.sequence
        for offset in range(0, len(seq), _LINE_WIDTH):
            coordinate_1based = offset + 1
            chunk = seq[offset : offset + _LINE_WIDTH]
            lines.append(f"{coordinate_1based:>10} {chunk}")
        self._text_edit.setPlainText("\n".join(lines))

    @property
    def current_record(self) -> SequenceRecord | None:
        return self._record
