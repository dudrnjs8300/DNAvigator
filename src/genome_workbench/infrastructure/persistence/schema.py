"""SQLite project schema. Migrations are forward-only via PRAGMA user_version."""

from __future__ import annotations

import sqlite3

CURRENT_SCHEMA_VERSION = 2

_SCHEMA_V1 = """
CREATE TABLE project (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    schema_version INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    modified_at TEXT NOT NULL,
    app_version TEXT NOT NULL,
    settings_json TEXT NOT NULL DEFAULT '{}',
    source_manifest TEXT NOT NULL DEFAULT '[]'
);

CREATE TABLE sequence_record (
    id TEXT PRIMARY KEY,
    display_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    molecule_type TEXT NOT NULL,
    topology TEXT NOT NULL,
    sequence TEXT NOT NULL,
    checksum_sha256 TEXT NOT NULL,
    annotations_json TEXT NOT NULL DEFAULT '{}',
    source_format TEXT NOT NULL DEFAULT '',
    source_record_index INTEGER NOT NULL DEFAULT 0,
    revision INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE provenance (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    tool_name TEXT,
    tool_version TEXT,
    database_id TEXT,
    database_checksum TEXT,
    query_checksum TEXT,
    parameters_json TEXT,
    subject_id TEXT,
    identity REAL,
    query_coverage REAL,
    subject_coverage REAL,
    evalue REAL,
    bitscore REAL,
    raw_result_ref TEXT,
    created_at TEXT NOT NULL,
    user_note TEXT
);

CREATE TABLE feature (
    id TEXT PRIMARY KEY,
    record_id TEXT NOT NULL REFERENCES sequence_record(id) ON DELETE CASCADE,
    type TEXT NOT NULL,
    strand INTEGER,
    location_operator TEXT NOT NULL,
    display_label TEXT,
    source TEXT,
    score REAL,
    phase INTEGER,
    provenance_id TEXT REFERENCES provenance(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL,
    modified_at TEXT NOT NULL,
    revision INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX idx_feature_record_id ON feature(record_id);

CREATE TABLE location_part (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    feature_id TEXT NOT NULL REFERENCES feature(id) ON DELETE CASCADE,
    start0 INTEGER NOT NULL,
    end0 INTEGER NOT NULL,
    order_index INTEGER NOT NULL,
    fuzzy_start INTEGER NOT NULL DEFAULT 0,
    fuzzy_end INTEGER NOT NULL DEFAULT 0,
    phase INTEGER
);
CREATE INDEX idx_location_part_feature_id ON location_part(feature_id);

CREATE TABLE qualifier (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    feature_id TEXT NOT NULL REFERENCES feature(id) ON DELETE CASCADE,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    seq_index INTEGER NOT NULL
);
CREATE INDEX idx_qualifier_feature_id ON qualifier(feature_id);

CREATE TABLE feature_relationship (
    parent_id TEXT NOT NULL REFERENCES feature(id) ON DELETE CASCADE,
    child_id TEXT NOT NULL REFERENCES feature(id) ON DELETE CASCADE,
    PRIMARY KEY (parent_id, child_id)
);

CREATE TABLE audit_event (
    id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    summary TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX idx_audit_event_created_at ON audit_event(created_at);
"""

_SCHEMA_V2 = """
CREATE TABLE folder (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    parent_folder_id TEXT,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE INDEX idx_folder_parent ON folder(parent_folder_id);

ALTER TABLE sequence_record ADD COLUMN folder_id TEXT;
CREATE INDEX idx_sequence_record_folder_id ON sequence_record(folder_id);
"""

_MIGRATIONS: dict[int, str] = {
    1: _SCHEMA_V1,
    2: _SCHEMA_V2,
}


def initialize_schema(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA foreign_keys = ON")
    current_version = conn.execute("PRAGMA user_version").fetchone()[0]
    if current_version >= CURRENT_SCHEMA_VERSION:
        return
    for version in range(current_version + 1, CURRENT_SCHEMA_VERSION + 1):
        conn.executescript(_MIGRATIONS[version])
        conn.execute(f"PRAGMA user_version = {version}")
    conn.commit()


def get_schema_version(conn: sqlite3.Connection) -> int:
    return conn.execute("PRAGMA user_version").fetchone()[0]
