"""Owns the currently-open project: repository lifecycle, locking, undo stack, audit log."""

from __future__ import annotations

from pathlib import Path

from genome_workbench.application.commands import UndoStack
from genome_workbench.domain.events import AuditEvent, EventType
from genome_workbench.domain.models import Feature, Project, SequenceRecord, Topology, utc_now
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

    def touch(self) -> None:
        self._require_repo().touch_project(utc_now())

    def log_audit(self, event_type: str, entity_id: str, summary: str) -> None:
        self._require_repo().append_audit_event(
            AuditEvent(event_type=event_type, entity_id=entity_id, summary=summary)
        )
