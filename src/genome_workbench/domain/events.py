"""Audit event records — one row per mutating action, for project audit history."""

from __future__ import annotations

from dataclasses import dataclass, field

from genome_workbench.domain.models import new_id, utc_now


class EventType:
    IMPORT = "import"
    FEATURE_CREATE = "feature_create"
    FEATURE_UPDATE = "feature_update"
    FEATURE_DELETE = "feature_delete"
    RECORD_DELETE = "record_delete"
    SEQUENCE_OPERATION = "sequence_operation"
    BLAST_DATABASE_CREATE = "blast_database_create"
    BLAST_RUN = "blast_run"
    BLAST_ANNOTATION_APPLY = "blast_annotation_apply"
    PROJECT_MIGRATION = "project_migration"
    EXPORT = "export"
    FOLDER_CREATE = "folder_create"
    FOLDER_UPDATE = "folder_update"
    FOLDER_DELETE = "folder_delete"


@dataclass(slots=True)
class AuditEvent:
    id: str = field(default_factory=new_id)
    event_type: str = ""
    entity_id: str = ""
    summary: str = ""
    created_at: str = field(default_factory=utc_now)
