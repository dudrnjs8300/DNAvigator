"""Owns the currently-open project: repository lifecycle, undo stack, audit log."""

from __future__ import annotations

from pathlib import Path

from genome_workbench.application.commands import UndoStack
from genome_workbench.domain.events import AuditEvent, EventType
from genome_workbench.domain.models import Feature, Project, SequenceRecord, Topology, utc_now
from genome_workbench.infrastructure.persistence.sqlite_repository import ProjectRepository
from genome_workbench.version import APP_VERSION


class NoOpenProjectError(RuntimeError):
    pass


class ProjectService:
    def __init__(self) -> None:
        self._repo: ProjectRepository | None = None
        self._path: Path | None = None
        self.undo_stack = UndoStack()

    @property
    def is_open(self) -> bool:
        return self._repo is not None

    @property
    def path(self) -> Path | None:
        return self._path

    def _require_repo(self) -> ProjectRepository:
        if self._repo is None:
            raise NoOpenProjectError("no project is currently open")
        return self._repo

    def create_new(self, path: Path, name: str) -> Project:
        self.close()
        project = Project(name=name, app_version=APP_VERSION)
        self._repo = ProjectRepository.create_new(path, project)
        self._path = Path(path)
        self.undo_stack.clear()
        return project

    def open(self, path: Path) -> Project:
        self.close()
        self._repo = ProjectRepository.open_existing(path)
        self._path = Path(path)
        self.undo_stack.clear()
        return self._repo.get_project()

    def close(self) -> None:
        if self._repo is not None:
            self._repo.close()
        self._repo = None
        self._path = None
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
        repo = self._require_repo()
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
