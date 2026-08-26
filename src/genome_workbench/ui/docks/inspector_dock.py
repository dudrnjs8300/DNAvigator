"""Right dock: feature/record detail inspector.

P0/Phase 1 implementation shows a read-only detail view. The full editable
qualifier form/table editor (spec 7.6) is Phase 4 scope.
"""

from __future__ import annotations

from PySide6.QtWidgets import QDockWidget, QPlainTextEdit

from genome_workbench.domain.coordinates import display_from_internal
from genome_workbench.domain.models import Feature, SequenceRecord


class InspectorDock(QDockWidget):
    def __init__(self, parent=None) -> None:
        super().__init__("Inspector", parent)
        self._text = QPlainTextEdit()
        self._text.setReadOnly(True)
        self.setWidget(self._text)

    def show_record(self, record: SequenceRecord) -> None:
        lines = [
            f"Record: {record.display_id}",
            f"Name: {record.name}",
            f"Description: {record.description}",
            f"Molecule type: {record.molecule_type.value}",
            f"Topology: {record.topology.value}",
            f"Length: {record.length} bp",
        ]
        self._text.setPlainText("\n".join(lines))

    def show_feature(self, feature: Feature, record: SequenceRecord) -> None:
        start_display, end_display = display_from_internal(feature.start0, feature.end0)
        strand_map = {1: "+", -1: "-", 0: "unknown", None: "unknown"}
        strand_text = strand_map.get(feature.strand, "unknown")
        lines = [
            f"Feature: {feature.computed_label()}",
            f"Type: {feature.type}",
            f"Location: {start_display}..{end_display} (1-based inclusive)",
            f"Strand: {strand_text}",
            f"Length: {feature.length} bp",
            f"Location operator: {feature.location_operator.value}",
            "",
            "Qualifiers:",
        ]
        for key, values in feature.qualifiers.items():
            for value in values:
                lines.append(f"  /{key}={value!r}" if value else f"  /{key}")
        self._text.setPlainText("\n".join(lines))

    def clear(self) -> None:
        self._text.setPlainText("")
