"""Owns the currently-open project: repository lifecycle, locking, undo stack, audit log."""

from __future__ import annotations

from pathlib import Path

from genome_workbench.application.commands import UndoStack
from genome_workbench.domain.events import AuditEvent, EventType
from genome_workbench.domain.models import (
    Feature,
    Folder,
    Project,
    SequenceRecord,
    Topology,
    utc_now,
)
from genome_workbench.infrastructure.filesystem import project_lock
from genome_workbench.infrastructure.persistence.sqlite_repository import ProjectRepository
from genome_workbench.version import APP_VERSION


class NoOpenProjectError(RuntimeError):
    pass


class ProjectReadOnlyError(RuntimeError):
    pass


class ProjectService:
    def __init__(self) -> None:
        self._repo: ProjectRepository | None = None
        self._path: Path | None = None
        self._read_only = False
        self.undo_stack = UndoStack()

    @property
    def is_open(self) -> bool:
        return self._repo is not None

    @property
    def is_read_only(self) -> bool:
        return self._read_only

    @property
    def path(self) -> Path | None:
        return self._path

    def _require_repo(self) -> ProjectRepository:
        if self._repo is None:
            raise NoOpenProjectError("no project is currently open")
        return self._repo

    def require_writable(self) -> ProjectRepository:
        repo = self._require_repo()
        if self._read_only:
            raise ProjectReadOnlyError(
                "this project is open read-only (another instance has it open, or it was "
                "not the one that acquired the lock); close it and reopen to make changes"
            )
        return repo

    def create_new(self, path: Path, name: str) -> Project:
        self.close()
        path = Path(path)
        project = Project(name=name, app_version=APP_VERSION)
        self._repo = ProjectRepository.create_new(path, project)
        project_lock.acquire_lock(path)
        self._path = path
        self._read_only = False
        self.undo_stack.clear()
        return project

    def open(self, path: Path, force: bool = False, read_only: bool = False) -> Project:
        self.close()
        path = Path(path)
        if not read_only:
            existing_lock = project_lock.read_lock(path)
            if existing_lock is not None and not force:
                raise project_lock.ProjectLockedError(existing_lock)
            project_lock.acquire_lock(path)
        self._repo = ProjectRepository.open_existing(path)
        self._path = path
        self._read_only = read_only
        self.undo_stack.clear()
        return self._repo.get_project()

    def close(self) -> None:
        if self._repo is not None:
            self._repo.close()
            if self._path is not None and not self._read_only:
                project_lock.release_lock(self._path)
        self._repo = None
        self._path = None
        self._read_only = False
        self.undo_stack.clear()

    def get_repository(self) -> ProjectRepository:
        return self._require_repo()

    def list_records(self) -> list[SequenceRecord]:
        return self._require_repo().list_records()

    def get_record(self, record_id: str) -> SequenceRecord | None:
        return self._require_repo().get_record(record_id)

    def list_features(self, record_id: str) -> list[Feature]:
        return self._require_repo().list_features(record_id)

    def delete_record(self, record_id: str) -> None:
        repo = self.require_writable()
        record = repo.get_record(record_id)
        if record is None:
            raise NoOpenProjectError(f"record {record_id} not found")
        feature_count = len(repo.list_features(record_id))
        repo.delete_record(record_id)
        self.log_audit(
            EventType.RECORD_DELETE,
            record_id,
            f"Deleted record '{record.display_id}' ({feature_count} feature(s) removed with it)",
        )
        self.touch()

    def set_record_topology(self, record_id: str, topology: Topology) -> SequenceRecord:
        repo = self.require_writable()
        record = repo.get_record(record_id)
        if record is None:
            raise NoOpenProjectError(f"record {record_id} not found")
        record.topology = topology
        repo.save_record(record)
        self.log_audit(EventType.FEATURE_UPDATE, record_id, f"Set topology to {topology.value}")
        self.touch()
        return record

    # -- Folders ---------------------------------------------------------------

    def list_folders(self) -> list[Folder]:
        return self._require_repo().list_folders()

    def create_folder(self, name: str, parent_folder_id: str | None = None) -> Folder:
        repo = self.require_writable()
        folder = Folder(name=name, parent_folder_id=parent_folder_id)
        repo.save_folder(folder)
        self.log_audit(EventType.FOLDER_CREATE, folder.id, f"Created folder '{name}'")
        self.touch()
        return folder

    def rename_folder(self, folder_id: str, new_name: str) -> Folder:
        repo = self.require_writable()
        folder = repo.get_folder(folder_id)
        if folder is None:
            raise NoOpenProjectError(f"folder {folder_id} not found")
        old_name = folder.name
        folder.name = new_name
        repo.save_folder(folder)
        self.log_audit(
            EventType.FOLDER_UPDATE, folder_id, f"Renamed folder '{old_name}' to '{new_name}'"
        )
        self.touch()
        return folder

    def delete_folder(self, folder_id: str) -> None:
        """Removes the folder but never the records/subfolders inside it --
        they move up to the deleted folder's parent (or to the root)."""
        repo = self.require_writable()
        folder = repo.get_folder(folder_id)
        if folder is None:
            raise NoOpenProjectError(f"folder {folder_id} not found")
        new_parent = folder.parent_folder_id
        for child_folder in repo.list_folders():
            if child_folder.parent_folder_id == folder_id:
                child_folder.parent_folder_id = new_parent
                repo.save_folder(child_folder)
        for record in repo.list_records():
            if record.folder_id == folder_id:
                record.folder_id = new_parent
                repo.save_record(record)
        repo.delete_folder(folder_id)
        self.log_audit(EventType.FOLDER_DELETE, folder_id, f"Deleted folder '{folder.name}'")
        self.touch()

    def move_record_to_folder(self, record_id: str, folder_id: str | None) -> SequenceRecord:
        repo = self.require_writable()
        record = repo.get_record(record_id)
        if record is None:
            raise NoOpenProjectError(f"record {record_id} not found")
        record.folder_id = folder_id
        repo.save_record(record)
        self.log_audit(EventType.FOLDER_UPDATE, record_id, f"Moved record '{record.display_id}'")
        self.touch()
        return record

    def move_folder(self, folder_id: str, new_parent_folder_id: str | None) -> Folder:
        repo = self.require_writable()
        folder = repo.get_folder(folder_id)
        if folder is None:
            raise NoOpenProjectError(f"folder {folder_id} not found")
        if new_parent_folder_id == folder_id:
            raise ValueError("a folder cannot be moved into itself")
        by_id = {f.id: f for f in repo.list_folders()}
        cursor = new_parent_folder_id
        seen: set[str] = set()
        while cursor is not None:
            if cursor == folder_id:
                raise ValueError("a folder cannot be moved into one of its own subfolders")
            if cursor in seen:
                break
            seen.add(cursor)
            parent = by_id.get(cursor)
            cursor = parent.parent_folder_id if parent is not None else None
        folder.parent_folder_id = new_parent_folder_id
        repo.save_folder(folder)
        self.log_audit(EventType.FOLDER_UPDATE, folder_id, f"Moved folder '{folder.name}'")
        self.touch()
        return folder

    def touch(self) -> None:
        self._require_repo().touch_project(utc_now())

    def log_audit(self, event_type: str, entity_id: str, summary: str) -> None:
        self._require_repo().append_audit_event(
            AuditEvent(event_type=event_type, entity_id=entity_id, summary=summary)
        )
