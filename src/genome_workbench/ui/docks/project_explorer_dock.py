from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QDockWidget, QTreeWidget, QTreeWidgetItem

from genome_workbench.domain.models import SequenceRecord


class ProjectExplorerDock(QDockWidget):
    recordSelected = Signal(str)  # record id

    def __init__(self, parent=None) -> None:
        super().__init__("Project Explorer", parent)
        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["Record", "Type", "Length", "Topology"])
        self._tree.itemSelectionChanged.connect(self._on_selection_changed)
        self.setWidget(self._tree)

    def set_records(self, records: list[SequenceRecord]) -> None:
        self._tree.clear()
        for record in records:
            item = QTreeWidgetItem(
                [
                    record.display_id or record.name or "(unnamed)",
                    record.molecule_type.value,
                    str(record.length),
                    record.topology.value,
                ]
            )
            item.setData(0, Qt.ItemDataRole.UserRole, record.id)
            self._tree.addTopLevelItem(item)

    def _on_selection_changed(self) -> None:
        items = self._tree.selectedItems()
        if items:
            record_id = items[0].data(0, Qt.ItemDataRole.UserRole)
            if record_id:
                self.recordSelected.emit(record_id)
