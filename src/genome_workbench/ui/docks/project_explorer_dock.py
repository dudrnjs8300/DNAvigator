from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QDockWidget, QMenu, QTreeWidget, QTreeWidgetItem

from genome_workbench.domain.models import SequenceRecord, Topology


class ProjectExplorerDock(QDockWidget):
    recordSelected = Signal(str)  # record id
    topologyChangeRequested = Signal(str, str)  # record id, new topology value

    def __init__(self, parent=None) -> None:
        super().__init__("Project Explorer", parent)
        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["Record", "Type", "Length", "Topology", "Features"])
        self._tree.itemSelectionChanged.connect(self._on_selection_changed)
        self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._on_context_menu)
        self.setWidget(self._tree)

    def set_records(
        self, records: list[SequenceRecord], feature_counts: dict[str, int] | None = None
    ) -> None:
        feature_counts = feature_counts or {}
        self._tree.clear()
        for record in records:
            item = QTreeWidgetItem(
                [
                    record.display_id or record.name or "(unnamed)",
                    record.molecule_type.value,
                    f"{record.length:,}",
                    record.topology.value,
                    str(feature_counts.get(record.id, 0)),
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

    def _on_context_menu(self, position) -> None:
        item = self._tree.itemAt(position)
        if item is None:
            return
        record_id = item.data(0, Qt.ItemDataRole.UserRole)
        if not record_id:
            return
        menu = QMenu(self)
        set_linear = menu.addAction("Set Linear")
        set_circular = menu.addAction("Set Circular")
        chosen = menu.exec(self._tree.viewport().mapToGlobal(position))
        if chosen is set_linear:
            self.topologyChangeRequested.emit(record_id, Topology.LINEAR.value)
        elif chosen is set_circular:
            self.topologyChangeRequested.emit(record_id, Topology.CIRCULAR.value)
