"""Left dock: a real, nestable folder tree over the project's records --
not just a flat list. Folders are purely organizational (deleting one never
deletes what's inside it, see application/project_service.py::delete_folder).
"""

from __future__ import annotations

from collections.abc import Iterator

from PySide6.QtCore import QEvent, QObject, Qt, Signal
from PySide6.QtGui import QKeyEvent, QKeySequence
from PySide6.QtWidgets import (
    QDockWidget,
    QInputDialog,
    QMenu,
    QMessageBox,
    QTreeWidget,
    QTreeWidgetItem,
    QWidget,
)

from genome_workbench.domain.models import Folder, SequenceRecord, Topology

_ITEM_TYPE_ROLE = Qt.ItemDataRole.UserRole + 1
_ROOT_CHOICE = "(Project root -- no folder)"


def _folder_paths(folders: list[Folder]) -> dict[str, str]:
    """Builds "Parent/Child" display paths for every folder, for use in pickers."""
    by_id = {f.id: f for f in folders}

    def path_for(folder_id: str) -> str:
        folder = by_id[folder_id]
        if folder.parent_folder_id is None or folder.parent_folder_id not in by_id:
            return folder.name
        return f"{path_for(folder.parent_folder_id)}/{folder.name}"

    return {f.id: path_for(f.id) for f in folders}


class ProjectExplorerDock(QDockWidget):
    recordSelected = Signal(str)  # record id
    topologyChangeRequested = Signal(str, str)  # record id, new topology value
    deleteRecordRequested = Signal(str)  # record id
    moveRecordToFolderRequested = Signal(str, str)  # record id, folder id ("" = root)
    createFolderRequested = Signal(str, str)  # name, parent folder id ("" = root)
    renameFolderRequested = Signal(str, str)  # folder id, new name
    deleteFolderRequested = Signal(str)  # folder id
    moveFolderRequested = Signal(str, str)  # folder id, new parent folder id ("" = root)
    pasteRegionRequested = Signal(str)  # target folder id ("" = root)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Project Explorer", parent)
        self._folders: list[Folder] = []
        self._records: list[SequenceRecord] = []

        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["Record", "Type", "Length", "Topology", "Features"])
        self._tree.itemSelectionChanged.connect(self._on_selection_changed)
        self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._on_context_menu)
        self._tree.installEventFilter(self)
        self.setWidget(self._tree)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if (
            watched is self._tree
            and event.type() == QEvent.Type.KeyPress
            and isinstance(event, QKeyEvent)
        ):
            if event.key() == Qt.Key.Key_Delete:
                self._on_delete_key_pressed()
                return True
            if event.matches(QKeySequence.StandardKey.Paste):
                self._on_paste_key_pressed()
                return True
        return super().eventFilter(watched, event)

    def _on_delete_key_pressed(self) -> None:
        items = self._tree.selectedItems()
        if not items:
            return
        item = items[0]
        item_type = item.data(0, _ITEM_TYPE_ROLE)
        item_id = item.data(0, Qt.ItemDataRole.UserRole)
        item_name = item.text(0)
        if item_type == "record":
            self._prompt_delete_record(item_id, item_name)
        elif item_type == "folder":
            self._prompt_delete_folder(item_id, item_name)

    def _on_paste_key_pressed(self) -> None:
        """Ctrl+V here pastes whatever region was last copied (Ctrl+C on the
        Genome Map / Circular Map) as a new record, placed into the folder
        that's currently selected -- or the folder containing the currently
        selected record, if a record rather than a folder is selected. Root
        ("") if nothing is selected or the selected record isn't in a folder.
        The actual paste is handled by MainWindow (which owns the copied
        region + project data); this only resolves the *destination*."""
        target_folder_id = ""
        items = self._tree.selectedItems()
        if items:
            item = items[0]
            item_type = item.data(0, _ITEM_TYPE_ROLE)
            item_id = item.data(0, Qt.ItemDataRole.UserRole)
            if item_type == "folder":
                target_folder_id = item_id
            elif item_type == "record":
                record = next((r for r in self._records if r.id == item_id), None)
                if record is not None and record.folder_id:
                    target_folder_id = record.folder_id
        self.pasteRegionRequested.emit(target_folder_id)

    def set_data(
        self,
        records: list[SequenceRecord],
        folders: list[Folder],
        feature_counts: dict[str, int] | None = None,
    ) -> None:
        feature_counts = feature_counts or {}
        self._records = records
        self._folders = folders

        expanded_folder_ids = {
            item.data(0, Qt.ItemDataRole.UserRole)
            for item in self._iter_all_items()
            if item.data(0, _ITEM_TYPE_ROLE) == "folder" and item.isExpanded()
        }
        selected_record_id = None
        current = self._tree.currentItem()
        if current is not None and current.data(0, _ITEM_TYPE_ROLE) == "record":
            selected_record_id = current.data(0, Qt.ItemDataRole.UserRole)

        self._tree.clear()

        folder_items: dict[str, QTreeWidgetItem] = {}

        def folder_item_for(folder_id: str) -> QTreeWidgetItem:
            if folder_id in folder_items:
                return folder_items[folder_id]
            folder = next(f for f in folders if f.id == folder_id)
            item = QTreeWidgetItem([folder.name])
            item.setData(0, Qt.ItemDataRole.UserRole, folder.id)
            item.setData(0, _ITEM_TYPE_ROLE, "folder")
            item.setIcon(0, self.style().standardIcon(self.style().StandardPixmap.SP_DirIcon))
            if folder.parent_folder_id is not None and any(
                f.id == folder.parent_folder_id for f in folders
            ):
                folder_item_for(folder.parent_folder_id).addChild(item)
            else:
                self._tree.addTopLevelItem(item)
            folder_items[folder_id] = item
            if folder_id in expanded_folder_ids:
                item.setExpanded(True)
            return item

        for folder in sorted(folders, key=lambda f: (f.sort_order, f.name)):
            folder_item_for(folder.id)

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
            item.setData(0, _ITEM_TYPE_ROLE, "record")
            if record.folder_id is not None and record.folder_id in folder_items:
                folder_item_for(record.folder_id).addChild(item)
            else:
                self._tree.addTopLevelItem(item)
            if record.id == selected_record_id:
                self._tree.setCurrentItem(item)

    def _iter_all_items(self) -> Iterator[QTreeWidgetItem]:
        def walk(item: QTreeWidgetItem) -> Iterator[QTreeWidgetItem]:
            yield item
            for i in range(item.childCount()):
                child = item.child(i)
                if child is not None:
                    yield from walk(child)

        for i in range(self._tree.topLevelItemCount()):
            top_item = self._tree.topLevelItem(i)
            if top_item is not None:
                yield from walk(top_item)

    def _on_selection_changed(self) -> None:
        items = self._tree.selectedItems()
        if items and items[0].data(0, _ITEM_TYPE_ROLE) == "record":
            record_id = items[0].data(0, Qt.ItemDataRole.UserRole)
            if record_id:
                self.recordSelected.emit(record_id)

    def _on_context_menu(self, position) -> None:
        # QMenu.exec() is a Shiboken-bound modal call that cannot be
        # monkeypatched from Python, so this method only builds+execs the menu
        # and maps the chosen action to a key; _dispatch_folder_action /
        # _dispatch_record_action carry the actual logic and are what tests
        # call directly (same split pattern as MainWindow's context menus).
        item = self._tree.itemAt(position)
        menu = QMenu(self)
        if item is None:
            new_folder = menu.addAction("New Folder...")
            chosen = menu.exec(self._tree.viewport().mapToGlobal(position))
            if chosen is new_folder:
                self._prompt_new_folder(parent_folder_id=None)
            return

        item_type = item.data(0, _ITEM_TYPE_ROLE)
        item_id = item.data(0, Qt.ItemDataRole.UserRole)
        item_name = item.text(0)

        if item_type == "folder":
            new_folder = menu.addAction("New Folder...")
            rename = menu.addAction("Rename Folder...")
            move = menu.addAction("Move to Folder...")
            menu.addSeparator()
            delete = menu.addAction("Delete Folder (keeps contents)")
            chosen = menu.exec(self._tree.viewport().mapToGlobal(position))
            key = {
                new_folder: "new_folder",
                rename: "rename",
                move: "move",
                delete: "delete",
            }.get(chosen)
            if key is not None:
                self._dispatch_folder_action(key, item_id, item_name)
            return

        set_linear = menu.addAction("Set Linear")
        set_circular = menu.addAction("Set Circular")
        menu.addSeparator()
        move_to_folder = menu.addAction("Move to Folder...")
        menu.addSeparator()
        delete_record = menu.addAction("Delete Record...")
        chosen = menu.exec(self._tree.viewport().mapToGlobal(position))
        key = {
            set_linear: "set_linear",
            set_circular: "set_circular",
            move_to_folder: "move_to_folder",
            delete_record: "delete_record",
        }.get(chosen)
        if key is not None:
            self._dispatch_record_action(key, item_id, item_name)

    def _dispatch_folder_action(self, key: str, folder_id: str, folder_name: str) -> None:
        if key == "new_folder":
            self._prompt_new_folder(parent_folder_id=folder_id)
        elif key == "rename":
            self._prompt_rename_folder(folder_id, folder_name)
        elif key == "move":
            self._prompt_move_folder(folder_id)
        elif key == "delete":
            self._prompt_delete_folder(folder_id, folder_name)

    def _dispatch_record_action(self, key: str, record_id: str, record_name: str) -> None:
        if key == "set_linear":
            self.topologyChangeRequested.emit(record_id, Topology.LINEAR.value)
        elif key == "set_circular":
            self.topologyChangeRequested.emit(record_id, Topology.CIRCULAR.value)
        elif key == "move_to_folder":
            self._prompt_move_record(record_id)
        elif key == "delete_record":
            self._prompt_delete_record(record_id, record_name)

    # -- Prompts (pure UI interaction; the actual mutation happens in MainWindow) --

    def _prompt_new_folder(self, parent_folder_id: str | None) -> None:
        name, ok = QInputDialog.getText(self, "New Folder", "Folder name:")
        if ok and name.strip():
            self.createFolderRequested.emit(name.strip(), parent_folder_id or "")

    def _prompt_rename_folder(self, folder_id: str, current_name: str) -> None:
        name, ok = QInputDialog.getText(self, "Rename Folder", "New name:", text=current_name)
        if ok and name.strip():
            self.renameFolderRequested.emit(folder_id, name.strip())

    def _prompt_delete_folder(self, folder_id: str, name: str) -> None:
        answer = QMessageBox.question(
            self,
            "Delete Folder",
            f'Delete folder "{name}"? Records and subfolders inside it will move up '
            "one level -- nothing is deleted except the folder itself.",
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.deleteFolderRequested.emit(folder_id)

    def _prompt_delete_record(self, record_id: str, name: str) -> None:
        answer = QMessageBox.warning(
            self,
            "Delete Record",
            f'Permanently delete "{name}" and all of its annotations from this project?\n\n'
            "This cannot be undone. The original imported file on disk is not affected.",
            buttons=QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            defaultButton=QMessageBox.StandardButton.Cancel,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.deleteRecordRequested.emit(record_id)

    def _prompt_move_record(self, record_id: str) -> None:
        target = self._choose_folder(exclude_folder_id=None)
        if target is not None:
            self.moveRecordToFolderRequested.emit(record_id, target)

    def _prompt_move_folder(self, folder_id: str) -> None:
        target = self._choose_folder(exclude_folder_id=folder_id)
        if target is not None:
            self.moveFolderRequested.emit(folder_id, target)

    def _choose_folder(self, exclude_folder_id: str | None) -> str | None:
        paths = _folder_paths(self._folders)
        choices = [_ROOT_CHOICE] + [paths[f.id] for f in self._folders if f.id != exclude_folder_id]
        id_by_path = {v: k for k, v in paths.items()}
        choice, ok = QInputDialog.getItem(
            self, "Move to Folder", "Destination:", choices, editable=False
        )
        if not ok:
            return None
        if choice == _ROOT_CHOICE:
            return ""
        return id_by_path.get(choice, "")
