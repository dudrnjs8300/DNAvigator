"""SQLite-backed project repository. The only place raw SQL is written.

All queries use parameter binding — never string-interpolated SQL.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from genome_workbench.domain.events import AuditEvent
from genome_workbench.domain.locations import LocationOperator, LocationPart
from genome_workbench.domain.models import (
    Feature,
    Folder,
    MoleculeType,
    Project,
    Provenance,
    ProvenanceKind,
    SequenceRecord,
    Topology,
)
from genome_workbench.domain.qualifiers import QualifierSet
from genome_workbench.infrastructure.persistence.schema import initialize_schema


class ProjectRepositoryError(RuntimeError):
    pass


class ProjectRepository:
    """One SQLite connection per open project (``.gwbproj`` file)."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")

    @classmethod
    def create_new(cls, path: Path, project: Project) -> ProjectRepository:
        path = Path(path)
        if path.exists():
            raise ProjectRepositoryError(f"project file already exists: {path}")
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(path))
        initialize_schema(conn)
        repo = cls(conn)
        repo._insert_project(project)
        conn.commit()
        return repo

    @classmethod
    def open_existing(cls, path: Path) -> ProjectRepository:
        path = Path(path)
        if not path.exists():
            raise ProjectRepositoryError(f"project file does not exist: {path}")
        conn = sqlite3.connect(str(path))
        initialize_schema(conn)
        return cls(conn)

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> ProjectRepository:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- Project -----------------------------------------------------------

    def _insert_project(self, project: Project) -> None:
        self._conn.execute(
            """INSERT INTO project
               (id, name, schema_version, created_at, modified_at, app_version,
                settings_json, source_manifest)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                project.id,
                project.name,
                project.schema_version,
                project.created_at,
                project.modified_at,
                project.app_version,
                project.settings_json,
                project.source_manifest,
            ),
        )

    def get_project(self) -> Project:
        row = self._conn.execute("SELECT * FROM project LIMIT 1").fetchone()
        if row is None:
            raise ProjectRepositoryError("project row missing")
        return Project(
            id=row["id"],
            name=row["name"],
            schema_version=row["schema_version"],
            created_at=row["created_at"],
            modified_at=row["modified_at"],
            app_version=row["app_version"],
            settings_json=row["settings_json"],
            source_manifest=row["source_manifest"],
        )

    def touch_project(self, modified_at: str) -> None:
        self._conn.execute("UPDATE project SET modified_at = ?", (modified_at,))
        self._conn.commit()

    # -- SequenceRecord ------------------------------------------------------

    def save_record(self, record: SequenceRecord, commit: bool = True) -> None:
        self._conn.execute(
            """INSERT INTO sequence_record
               (id, display_id, name, description, molecule_type, topology, sequence,
                checksum_sha256, annotations_json, source_format, source_record_index, revision,
                folder_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
                 display_id=excluded.display_id, name=excluded.name,
                 description=excluded.description, molecule_type=excluded.molecule_type,
                 topology=excluded.topology, sequence=excluded.sequence,
                 checksum_sha256=excluded.checksum_sha256,
                 annotations_json=excluded.annotations_json,
                 source_format=excluded.source_format,
                 source_record_index=excluded.source_record_index,
                 revision=excluded.revision,
                 folder_id=excluded.folder_id""",
            (
                record.id,
                record.display_id,
                record.name,
                record.description,
                record.molecule_type.value,
                record.topology.value,
                record.sequence,
                record.checksum_sha256,
                record.annotations_json,
                record.source_format,
                record.source_record_index,
                record.revision,
                record.folder_id,
            ),
        )
        if commit:
            self._conn.commit()

    def save_records_bulk(self, records: list[SequenceRecord]) -> None:
        """Saves many records in a single transaction/commit instead of one
        fsync per record -- see save_features_bulk for why this matters."""
        for record in records:
            self.save_record(record, commit=False)
        self._conn.commit()

    def get_record(self, record_id: str) -> SequenceRecord | None:
        row = self._conn.execute(
            "SELECT * FROM sequence_record WHERE id = ?", (record_id,)
        ).fetchone()
        return self._row_to_record(row) if row else None

    def list_records(self) -> list[SequenceRecord]:
        rows = self._conn.execute(
            "SELECT * FROM sequence_record ORDER BY source_record_index, id"
        ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def delete_record(self, record_id: str) -> None:
        self._conn.execute("DELETE FROM sequence_record WHERE id = ?", (record_id,))
        self._conn.commit()

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> SequenceRecord:
        return SequenceRecord(
            id=row["id"],
            display_id=row["display_id"],
            name=row["name"],
            description=row["description"],
            molecule_type=MoleculeType(row["molecule_type"]),
            topology=Topology(row["topology"]),
            sequence=row["sequence"],
            checksum_sha256=row["checksum_sha256"],
            annotations_json=row["annotations_json"],
            source_format=row["source_format"],
            source_record_index=row["source_record_index"],
            revision=row["revision"],
            folder_id=row["folder_id"],
        )

    # -- Folder ----------------------------------------------------------------

    def save_folder(self, folder: Folder) -> None:
        self._conn.execute(
            """INSERT INTO folder (id, name, parent_folder_id, sort_order, created_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
                 name=excluded.name, parent_folder_id=excluded.parent_folder_id,
                 sort_order=excluded.sort_order""",
            (folder.id, folder.name, folder.parent_folder_id, folder.sort_order, folder.created_at),
        )
        self._conn.commit()

    def get_folder(self, folder_id: str) -> Folder | None:
        row = self._conn.execute("SELECT * FROM folder WHERE id = ?", (folder_id,)).fetchone()
        return self._row_to_folder(row) if row else None

    def list_folders(self) -> list[Folder]:
        rows = self._conn.execute("SELECT * FROM folder ORDER BY sort_order, name").fetchall()
        return [self._row_to_folder(row) for row in rows]

    def delete_folder(self, folder_id: str) -> None:
        self._conn.execute("DELETE FROM folder WHERE id = ?", (folder_id,))
        self._conn.commit()

    @staticmethod
    def _row_to_folder(row: sqlite3.Row) -> Folder:
        return Folder(
            id=row["id"],
            name=row["name"],
            parent_folder_id=row["parent_folder_id"],
            sort_order=row["sort_order"],
            created_at=row["created_at"],
        )

    # -- Provenance ----------------------------------------------------------

    def save_provenance(self, provenance: Provenance) -> None:
        self._conn.execute(
            """INSERT INTO provenance
               (id, kind, tool_name, tool_version, database_id, database_checksum,
                query_checksum, parameters_json, subject_id, identity, query_coverage,
                subject_coverage, evalue, bitscore, raw_result_ref, created_at, user_note)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO NOTHING""",
            (
                provenance.id,
                provenance.kind.value,
                provenance.tool_name,
                provenance.tool_version,
                provenance.database_id,
                provenance.database_checksum,
                provenance.query_checksum,
                provenance.parameters_json,
                provenance.subject_id,
                provenance.identity,
                provenance.query_coverage,
                provenance.subject_coverage,
                provenance.evalue,
                provenance.bitscore,
                provenance.raw_result_ref,
                provenance.created_at,
                provenance.user_note,
            ),
        )

    def get_provenance(self, provenance_id: str) -> Provenance | None:
        row = self._conn.execute(
            "SELECT * FROM provenance WHERE id = ?", (provenance_id,)
        ).fetchone()
        if row is None:
            return None
        return Provenance(
            id=row["id"],
            kind=ProvenanceKind(row["kind"]),
            tool_name=row["tool_name"],
            tool_version=row["tool_version"],
            database_id=row["database_id"],
            database_checksum=row["database_checksum"],
            query_checksum=row["query_checksum"],
            parameters_json=row["parameters_json"],
            subject_id=row["subject_id"],
            identity=row["identity"],
            query_coverage=row["query_coverage"],
            subject_coverage=row["subject_coverage"],
            evalue=row["evalue"],
            bitscore=row["bitscore"],
            raw_result_ref=row["raw_result_ref"],
            created_at=row["created_at"],
            user_note=row["user_note"],
        )

    # -- Feature ---------------------------------------------------------------

    def save_feature(self, feature: Feature, commit: bool = True) -> None:
        if feature.provenance_id is not None:
            existing = self.get_provenance(feature.provenance_id)
            if existing is None:
                raise ProjectRepositoryError(
                    f"feature {feature.id} references unknown provenance {feature.provenance_id}"
                )
        self._conn.execute(
            """INSERT INTO feature
               (id, record_id, type, strand, location_operator, display_label, source,
                score, phase, provenance_id, created_at, modified_at, revision)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
                 record_id=excluded.record_id, type=excluded.type, strand=excluded.strand,
                 location_operator=excluded.location_operator,
                 display_label=excluded.display_label, source=excluded.source,
                 score=excluded.score, phase=excluded.phase,
                 provenance_id=excluded.provenance_id, modified_at=excluded.modified_at,
                 revision=excluded.revision""",
            (
                feature.id,
                feature.record_id,
                feature.type,
                feature.strand,
                feature.location_operator.value,
                feature.display_label,
                feature.source,
                feature.score,
                feature.phase,
                feature.provenance_id,
                feature.created_at,
                feature.modified_at,
                feature.revision,
            ),
        )
        self._conn.execute("DELETE FROM location_part WHERE feature_id = ?", (feature.id,))
        for part in feature.parts:
            self._conn.execute(
                """INSERT INTO location_part
                   (feature_id, start0, end0, order_index, fuzzy_start, fuzzy_end, phase)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    feature.id,
                    part.start0,
                    part.end0,
                    part.order_index,
                    int(part.fuzzy_start),
                    int(part.fuzzy_end),
                    part.phase,
                ),
            )
        self._conn.execute("DELETE FROM qualifier WHERE feature_id = ?", (feature.id,))
        seq_index = 0
        for key, values in feature.qualifiers.items():
            for value in values:
                self._conn.execute(
                    "INSERT INTO qualifier (feature_id, key, value, seq_index) VALUES (?, ?, ?, ?)",
                    (feature.id, key, value, seq_index),
                )
                seq_index += 1
        self._conn.execute("DELETE FROM feature_relationship WHERE parent_id = ?", (feature.id,))
        for child_id in feature.child_ids:
            self._conn.execute(
                "INSERT OR IGNORE INTO feature_relationship (parent_id, child_id) VALUES (?, ?)",
                (feature.id, child_id),
            )
        if commit:
            self._conn.commit()

    def save_features_bulk(self, features: list[Feature]) -> None:
        """Saves many features in a single transaction/commit instead of one
        fsync per feature. A single-feature commit forces a disk sync
        (SQLite's default synchronous mode), which is the right tradeoff for
        one user edit at a time (D-009: immediate commit means there's no
        "unsaved" state to lose) but made importing thousands of features
        from a GenBank/GFF3 file dramatically slower than necessary --
        measured at ~86s for 6,000 features (spec 8.4 target: <=5s) before
        this existed, entirely spent on fsync overhead rather than actual
        work. See docs/PERFORMANCE.md.
        """
        for feature in features:
            self.save_feature(feature, commit=False)
        self._conn.commit()

    def get_feature(self, feature_id: str) -> Feature | None:
        row = self._conn.execute("SELECT * FROM feature WHERE id = ?", (feature_id,)).fetchone()
        if row is None:
            return None
        return self._row_to_feature(row)

    def list_features(self, record_id: str) -> list[Feature]:
        """Bulk-loads every feature for a record in a fixed number of
        queries (one JOIN per related table) instead of one round trip per
        related table *per feature*. The naive per-feature version issued
        4 extra queries for every feature -- 24,000+ queries for a 6,000
        feature record -- which measured at ~6.5s just to reopen a project
        (spec 8.4 target: <=500ms warm). See docs/PERFORMANCE.md.
        """
        feature_rows = self._conn.execute(
            "SELECT * FROM feature WHERE record_id = ? ORDER BY rowid", (record_id,)
        ).fetchall()
        if not feature_rows:
            return []

        parts_by_feature: dict[str, list[LocationPart]] = {}
        for p in self._conn.execute(
            """SELECT lp.* FROM location_part lp JOIN feature f ON lp.feature_id = f.id
               WHERE f.record_id = ? ORDER BY lp.feature_id, lp.order_index""",
            (record_id,),
        ).fetchall():
            parts_by_feature.setdefault(p["feature_id"], []).append(
                LocationPart(
                    start0=p["start0"],
                    end0=p["end0"],
                    order_index=p["order_index"],
                    fuzzy_start=bool(p["fuzzy_start"]),
                    fuzzy_end=bool(p["fuzzy_end"]),
                    phase=p["phase"],
                )
            )

        qualifiers_by_feature: dict[str, QualifierSet] = {}
        for q in self._conn.execute(
            """SELECT q.* FROM qualifier q JOIN feature f ON q.feature_id = f.id
               WHERE f.record_id = ? ORDER BY q.feature_id, q.seq_index""",
            (record_id,),
        ).fetchall():
            qualifiers_by_feature.setdefault(q["feature_id"], QualifierSet()).add(
                q["key"], q["value"]
            )

        children_by_feature: dict[str, list[str]] = {}
        for r in self._conn.execute(
            """SELECT fr.* FROM feature_relationship fr JOIN feature f ON fr.parent_id = f.id
               WHERE f.record_id = ?""",
            (record_id,),
        ).fetchall():
            children_by_feature.setdefault(r["parent_id"], []).append(r["child_id"])

        parents_by_feature: dict[str, list[str]] = {}
        for r in self._conn.execute(
            """SELECT fr.* FROM feature_relationship fr JOIN feature f ON fr.child_id = f.id
               WHERE f.record_id = ?""",
            (record_id,),
        ).fetchall():
            parents_by_feature.setdefault(r["child_id"], []).append(r["parent_id"])

        return [
            self._build_feature(
                row,
                parts_by_feature.get(row["id"], []),
                qualifiers_by_feature.get(row["id"], QualifierSet()),
                children_by_feature.get(row["id"], []),
                parents_by_feature.get(row["id"], []),
            )
            for row in feature_rows
        ]

    def delete_feature(self, feature_id: str) -> None:
        self._conn.execute("DELETE FROM feature WHERE id = ?", (feature_id,))
        self._conn.commit()

    def _row_to_feature(self, row: sqlite3.Row) -> Feature:
        feature_id = row["id"]
        parts = [
            LocationPart(
                start0=p["start0"],
                end0=p["end0"],
                order_index=p["order_index"],
                fuzzy_start=bool(p["fuzzy_start"]),
                fuzzy_end=bool(p["fuzzy_end"]),
                phase=p["phase"],
            )
            for p in self._conn.execute(
                "SELECT * FROM location_part WHERE feature_id = ? ORDER BY order_index",
                (feature_id,),
            ).fetchall()
        ]
        qualifiers = QualifierSet()
        for q in self._conn.execute(
            "SELECT key, value FROM qualifier WHERE feature_id = ? ORDER BY seq_index",
            (feature_id,),
        ).fetchall():
            qualifiers.add(q["key"], q["value"])
        child_ids = [
            r["child_id"]
            for r in self._conn.execute(
                "SELECT child_id FROM feature_relationship WHERE parent_id = ?",
                (feature_id,),
            ).fetchall()
        ]
        parent_ids = [
            r["parent_id"]
            for r in self._conn.execute(
                "SELECT parent_id FROM feature_relationship WHERE child_id = ?",
                (feature_id,),
            ).fetchall()
        ]
        return self._build_feature(row, parts, qualifiers, child_ids, parent_ids)

    @staticmethod
    def _build_feature(
        row: sqlite3.Row,
        parts: list[LocationPart],
        qualifiers: QualifierSet,
        child_ids: list[str],
        parent_ids: list[str],
    ) -> Feature:
        return Feature(
            id=row["id"],
            record_id=row["record_id"],
            type=row["type"],
            strand=row["strand"],
            location_operator=LocationOperator(row["location_operator"]),
            parts=parts,
            qualifiers=qualifiers,
            display_label=row["display_label"],
            parent_ids=parent_ids,
            child_ids=child_ids,
            source=row["source"],
            score=row["score"],
            phase=row["phase"],
            provenance_id=row["provenance_id"],
            created_at=row["created_at"],
            modified_at=row["modified_at"],
            revision=row["revision"],
        )

    # -- Audit -----------------------------------------------------------------

    def append_audit_event(self, event: AuditEvent) -> None:
        self._conn.execute(
            "INSERT INTO audit_event (id, event_type, entity_id, summary, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (event.id, event.event_type, event.entity_id, event.summary, event.created_at),
        )
        self._conn.commit()

    def list_audit_events(self) -> list[AuditEvent]:
        rows = self._conn.execute("SELECT * FROM audit_event ORDER BY created_at").fetchall()
        return [
            AuditEvent(
                id=r["id"],
                event_type=r["event_type"],
                entity_id=r["entity_id"],
                summary=r["summary"],
                created_at=r["created_at"],
            )
            for r in rows
        ]

    def integrity_check(self) -> bool:
        result = self._conn.execute("PRAGMA integrity_check").fetchone()
        return result[0] == "ok"
