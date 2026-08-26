import sqlite3
from pathlib import Path

import pytest

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
from genome_workbench.infrastructure.persistence.schema import _SCHEMA_V1, initialize_schema
from genome_workbench.infrastructure.persistence.sqlite_repository import (
    ProjectRepository,
    ProjectRepositoryError,
)


@pytest.fixture
def project_path(tmp_path: Path) -> Path:
    return tmp_path / "test project 한글 경로" / "sample.gwbproj"


def test_create_new_rejects_existing_file(tmp_path: Path):
    path = tmp_path / "a.gwbproj"
    path.write_text("x")
    with pytest.raises(ProjectRepositoryError):
        ProjectRepository.create_new(path, Project(name="X", app_version="0.1.0"))


def test_record_round_trip(project_path: Path):
    repo = ProjectRepository.create_new(project_path, Project(name="P", app_version="0.1.0"))
    record = SequenceRecord(
        display_id="contig1",
        name="contig1",
        description="test contig",
        molecule_type=MoleculeType.DNA,
        topology=Topology.LINEAR,
        sequence="ATGCCCTAA",
        checksum_sha256="deadbeef",
        source_format="fasta",
    )
    repo.save_record(record)
    repo.close()

    reopened = ProjectRepository.open_existing(project_path)
    fetched = reopened.get_record(record.id)
    assert fetched is not None
    assert fetched.sequence == "ATGCCCTAA"
    assert fetched.display_id == "contig1"
    assert fetched.molecule_type == MoleculeType.DNA
    reopened.close()


def test_feature_with_qualifiers_and_parts_round_trip(project_path: Path):
    repo = ProjectRepository.create_new(project_path, Project(name="P", app_version="0.1.0"))
    record = SequenceRecord(
        sequence="A" * 1000,
        checksum_sha256="x",
        molecule_type=MoleculeType.DNA,
    )
    repo.save_record(record)

    qualifiers = QualifierSet()
    qualifiers.add("gene", "exampleA")
    qualifiers.add("db_xref", "GO:001")
    qualifiers.add("db_xref", "GO:002")
    qualifiers.add("pseudo")

    feature = Feature(
        record_id=record.id,
        type="CDS",
        strand=1,
        location_operator=LocationOperator.JOIN,
        parts=[
            LocationPart(start0=100, end0=400, order_index=0),
            LocationPart(start0=500, end0=600, order_index=1),
        ],
        qualifiers=qualifiers,
    )
    repo.save_feature(feature)
    repo.close()

    reopened = ProjectRepository.open_existing(project_path)
    fetched = reopened.get_feature(feature.id)
    assert fetched is not None
    assert fetched.type == "CDS"
    assert fetched.strand == 1
    assert [p.start0 for p in fetched.parts] == [100, 500]
    assert [p.end0 for p in fetched.parts] == [400, 600]
    assert fetched.qualifiers.get("db_xref") == ["GO:001", "GO:002"]
    assert fetched.qualifiers.keys() == ["gene", "db_xref", "pseudo"]
    assert fetched.qualifiers.get("pseudo") == [""]
    reopened.close()


def test_delete_record_cascades_features(project_path: Path):
    repo = ProjectRepository.create_new(project_path, Project(name="P", app_version="0.1.0"))
    record = SequenceRecord(
        sequence="ACGT" * 100, checksum_sha256="x", molecule_type=MoleculeType.DNA
    )
    repo.save_record(record)
    feature = Feature(
        record_id=record.id,
        type="misc_feature",
        parts=[LocationPart(start0=0, end0=10, order_index=0)],
    )
    repo.save_feature(feature)

    repo.delete_record(record.id)
    assert repo.get_feature(feature.id) is None
    repo.close()


def test_provenance_round_trip_and_integrity(project_path: Path):
    repo = ProjectRepository.create_new(project_path, Project(name="P", app_version="0.1.0"))
    prov = Provenance(kind=ProvenanceKind.BLAST, tool_name="blastn", identity=98.5)
    repo.save_provenance(prov)
    repo._conn.commit()

    fetched = repo.get_provenance(prov.id)
    assert fetched is not None
    assert fetched.tool_name == "blastn"
    assert fetched.identity == pytest.approx(98.5)
    assert repo.integrity_check()
    repo.close()


def test_folder_round_trip_and_nesting(project_path: Path):
    repo = ProjectRepository.create_new(project_path, Project(name="P", app_version="0.1.0"))
    parent = Folder(name="Isolates")
    repo.save_folder(parent)
    child = Folder(name="2026 batch", parent_folder_id=parent.id)
    repo.save_folder(child)
    repo.close()

    reopened = ProjectRepository.open_existing(project_path)
    fetched_parent = reopened.get_folder(parent.id)
    fetched_child = reopened.get_folder(child.id)
    assert fetched_parent is not None
    assert fetched_parent.parent_folder_id is None
    assert fetched_child is not None
    assert fetched_child.parent_folder_id == parent.id
    assert {f.id for f in reopened.list_folders()} == {parent.id, child.id}
    reopened.close()


def test_record_folder_id_round_trip(project_path: Path):
    repo = ProjectRepository.create_new(project_path, Project(name="P", app_version="0.1.0"))
    folder = Folder(name="Isolates")
    repo.save_folder(folder)
    record = SequenceRecord(
        sequence="ACGT" * 100,
        checksum_sha256="x",
        molecule_type=MoleculeType.DNA,
        folder_id=folder.id,
    )
    repo.save_record(record)
    repo.close()

    reopened = ProjectRepository.open_existing(project_path)
    fetched = reopened.get_record(record.id)
    assert fetched is not None
    assert fetched.folder_id == folder.id
    reopened.close()

    # unfoldered records round-trip a None folder_id, not the string "None"
    repo2 = ProjectRepository.open_existing(project_path)
    other = SequenceRecord(sequence="AAAA", checksum_sha256="y", molecule_type=MoleculeType.DNA)
    repo2.save_record(other)
    repo2.close()
    repo3 = ProjectRepository.open_existing(project_path)
    assert repo3.get_record(other.id).folder_id is None
    repo3.close()


def test_delete_folder_does_not_cascade_to_folder_table_row_only(project_path: Path):
    repo = ProjectRepository.create_new(project_path, Project(name="P", app_version="0.1.0"))
    folder = Folder(name="Isolates")
    repo.save_folder(folder)
    repo.delete_folder(folder.id)
    assert repo.get_folder(folder.id) is None
    repo.close()


def test_v1_project_auto_migrates_to_v2_with_folder_support(project_path: Path):
    # Simulate a project file created before folders existed (schema v1 only)
    project_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(project_path))
    conn.executescript(_SCHEMA_V1)
    conn.execute("PRAGMA user_version = 1")
    conn.execute(
        "INSERT INTO project (id, name, schema_version, created_at, modified_at, app_version) "
        "VALUES ('p1', 'Old Project', 1, 'now', 'now', '0.0.9')"
    )
    conn.commit()
    conn.close()

    repo = ProjectRepository.open_existing(project_path)
    # the migration must not have lost the pre-existing project row
    assert repo.get_project().name == "Old Project"
    # and folder support must now work on this upgraded file
    folder = Folder(name="New folder on upgraded project")
    repo.save_folder(folder)
    assert repo.get_folder(folder.id) is not None
    repo.close()


def test_initialize_schema_is_idempotent(project_path: Path):
    project_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(project_path))
    initialize_schema(conn)
    initialize_schema(conn)  # must not raise or re-run migrations
    conn.close()


def test_feature_rejects_unknown_provenance(project_path: Path):
    repo = ProjectRepository.create_new(project_path, Project(name="P", app_version="0.1.0"))
    record = SequenceRecord(
        sequence="ACGT" * 100, checksum_sha256="x", molecule_type=MoleculeType.DNA
    )
    repo.save_record(record)
    feature = Feature(
        record_id=record.id,
        type="misc_feature",
        provenance_id="does-not-exist",
        parts=[LocationPart(start0=0, end0=10, order_index=0)],
    )
    with pytest.raises(ProjectRepositoryError):
        repo.save_feature(feature)
    repo.close()
