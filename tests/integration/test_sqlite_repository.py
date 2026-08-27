import sqlite3
from pathlib import Path

import pytest

from genome_workbench.domain.locations import LocationOperator, LocationPart
from genome_workbench.domain.models import (
    Alignment,
    AlignmentSequence,
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


def test_v2_project_auto_migrates_to_v3_with_alignment_support(project_path: Path):
    from genome_workbench.infrastructure.persistence.schema import _SCHEMA_V1, _SCHEMA_V2

    project_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(project_path))
    conn.executescript(_SCHEMA_V1)
    conn.executescript(_SCHEMA_V2)
    conn.execute("PRAGMA user_version = 2")
    conn.execute(
        "INSERT INTO project (id, name, schema_version, created_at, modified_at, app_version) "
        "VALUES ('p1', 'Old Project', 2, 'now', 'now', '0.3.0')"
    )
    conn.commit()
    conn.close()

    repo = ProjectRepository.open_existing(project_path)
    assert repo.get_project().name == "Old Project"
    alignment = Alignment(name="new on upgraded project", length=4)
    repo.save_alignment(
        alignment, [AlignmentSequence(alignment_id=alignment.id, label="s1", sequence="ACGT")]
    )
    assert repo.get_alignment(alignment.id) is not None
    repo.close()


def test_initialize_schema_is_idempotent(project_path: Path):
    project_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(project_path))
    initialize_schema(conn)
    initialize_schema(conn)  # must not raise or re-run migrations
    conn.close()


class _CountingConnection(sqlite3.Connection):
    """sqlite3.Connection is an immutable builtin type -- neither the class
    nor an instance can have `commit` monkeypatched onto it directly. A
    thin subclass is the only way to count commit() calls."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.commit_count = 0

    def commit(self) -> None:
        self.commit_count += 1
        super().commit()


def _repo_with_counting_connection(project_path: Path) -> ProjectRepository:
    project_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(project_path), factory=_CountingConnection)
    initialize_schema(conn)
    return ProjectRepository(conn)


def test_save_features_bulk_commits_once_not_per_feature(project_path: Path):
    """Regression test for the fix that took a 6,000-feature import from
    ~86s to <1s (spec 8.4 target: <=5s): save_feature commits (fsyncs) on
    every call, so a naive per-feature loop paid one fsync per feature.
    save_features_bulk must defer all commits to a single one at the end.
    """
    repo = _repo_with_counting_connection(project_path)
    record = SequenceRecord(
        sequence="A" * 10_000, checksum_sha256="x", molecule_type=MoleculeType.DNA
    )
    repo.save_record(record)
    features = [
        Feature(
            record_id=record.id,
            type="misc_feature",
            parts=[LocationPart(start0=i * 10, end0=i * 10 + 5, order_index=0)],
        )
        for i in range(50)
    ]

    repo._conn.commit_count = 0  # reset past the setup writes above
    repo.save_features_bulk(features)

    assert repo._conn.commit_count == 1
    assert len(repo.list_features(record.id)) == 50
    repo.close()


def test_save_records_bulk_commits_once_not_per_record(project_path: Path):
    repo = _repo_with_counting_connection(project_path)
    records = [
        SequenceRecord(
            display_id=f"contig{i}",
            sequence="ACGT" * 10,
            checksum_sha256="x",
            molecule_type=MoleculeType.DNA,
        )
        for i in range(20)
    ]

    repo._conn.commit_count = 0
    repo.save_records_bulk(records)

    assert repo._conn.commit_count == 1
    assert len(repo.list_records()) == 20
    repo.close()


def test_list_features_bulk_load_matches_per_feature_lookup_for_compound_and_related_features(
    project_path: Path,
):
    """Correctness check for the bulk-JOIN rewrite of list_features (the
    old version issued 4 extra queries per feature -- ~24,000 queries for
    6,000 features, measured at ~6.5s just to reopen a project; spec 8.4
    target: <=500ms warm). The new version must return identical data to
    get_feature() called one at a time, including for the edge cases that
    make grouping-by-feature-id easy to get subtly wrong: multi-part
    (compound) locations, multi-value qualifiers, parent/child
    relationships, and a feature with none of the above.
    """
    repo = ProjectRepository.create_new(project_path, Project(name="P", app_version="0.1.0"))
    record = SequenceRecord(
        sequence="A" * 10_000, checksum_sha256="x", molecule_type=MoleculeType.DNA
    )
    repo.save_record(record)

    bare = Feature(
        record_id=record.id, type="misc_feature", parts=[LocationPart(0, 10, order_index=0)]
    )
    qualifiers = QualifierSet()
    qualifiers.add("gene", "geneA")
    qualifiers.add("db_xref", "GO:001")
    qualifiers.add("db_xref", "GO:002")
    compound = Feature(
        record_id=record.id,
        type="CDS",
        strand=1,
        parts=[
            LocationPart(start0=100, end0=200, order_index=0),
            LocationPart(start0=300, end0=400, order_index=1),
        ],
        qualifiers=qualifiers,
    )
    child = Feature(record_id=record.id, type="mRNA", parts=[LocationPart(500, 600, order_index=0)])
    parent = Feature(
        record_id=record.id,
        type="gene",
        parts=[LocationPart(500, 600, order_index=0)],
        child_ids=[child.id],
    )
    repo.save_feature(bare)
    repo.save_feature(compound)
    repo.save_feature(child)
    repo.save_feature(parent)  # saving the parent's child_ids is what persists the relationship

    bulk = {f.id: f for f in repo.list_features(record.id)}
    assert set(bulk) == {bare.id, compound.id, parent.id, child.id}

    for feature_id in bulk:
        individually = repo.get_feature(feature_id)
        from_bulk = bulk[feature_id]
        assert [(p.start0, p.end0, p.order_index) for p in from_bulk.parts] == [
            (p.start0, p.end0, p.order_index) for p in individually.parts
        ]
        assert list(from_bulk.qualifiers.items()) == list(individually.qualifiers.items())
        assert sorted(from_bulk.child_ids) == sorted(individually.child_ids)
        assert sorted(from_bulk.parent_ids) == sorted(individually.parent_ids)

    assert bulk[child.id].parent_ids == [parent.id]
    assert bulk[parent.id].child_ids == [child.id]
    assert bulk[bare.id].parts == [LocationPart(0, 10, order_index=0)]
    assert bulk[bare.id].child_ids == []
    assert bulk[bare.id].parent_ids == []
    repo.close()


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


def test_alignment_round_trip(project_path: Path):
    repo = ProjectRepository.create_new(project_path, Project(name="P", app_version="0.1.0"))
    alignment = Alignment(
        name="msa1", molecule_type=MoleculeType.DNA, length=10, source_format="fasta"
    )
    sequences = [
        AlignmentSequence(
            alignment_id=alignment.id, label="seq1", sequence="ATG-CCGTAA", order_index=0
        ),
        AlignmentSequence(
            alignment_id=alignment.id, label="seq2", sequence="ATGACCGTAA", order_index=1
        ),
    ]
    repo.save_alignment(alignment, sequences)
    repo.close()

    reopened = ProjectRepository.open_existing(project_path)
    fetched = reopened.get_alignment(alignment.id)
    assert fetched is not None
    assert fetched.name == "msa1"
    assert fetched.length == 10
    fetched_sequences = reopened.list_alignment_sequences(alignment.id)
    assert [s.label for s in fetched_sequences] == ["seq1", "seq2"]
    assert [s.sequence for s in fetched_sequences] == ["ATG-CCGTAA", "ATGACCGTAA"]
    reopened.close()


def test_alignment_list_and_delete(project_path: Path):
    repo = ProjectRepository.create_new(project_path, Project(name="P", app_version="0.1.0"))
    a1 = Alignment(name="first", length=4)
    a2 = Alignment(name="second", length=4)
    repo.save_alignment(a1, [AlignmentSequence(alignment_id=a1.id, label="s1", sequence="ACGT")])
    repo.save_alignment(a2, [AlignmentSequence(alignment_id=a2.id, label="s1", sequence="ACGT")])

    assert {a.id for a in repo.list_alignments()} == {a1.id, a2.id}

    repo.delete_alignment(a1.id)
    assert repo.get_alignment(a1.id) is None
    assert repo.list_alignment_sequences(a1.id) == []
    assert {a.id for a in repo.list_alignments()} == {a2.id}
    repo.close()


def test_alignment_save_replaces_full_sequence_set(project_path: Path):
    """save_alignment always replaces every row -- there is no per-row
    incremental edit UI, so a re-save with fewer rows must drop the
    leftover rows rather than leaving them orphaned."""
    repo = ProjectRepository.create_new(project_path, Project(name="P", app_version="0.1.0"))
    alignment = Alignment(name="msa", length=4)
    repo.save_alignment(
        alignment,
        [
            AlignmentSequence(
                alignment_id=alignment.id, label="s1", sequence="ACGT", order_index=0
            ),
            AlignmentSequence(
                alignment_id=alignment.id, label="s2", sequence="ACGA", order_index=1
            ),
        ],
    )
    repo.save_alignment(
        alignment,
        [
            AlignmentSequence(
                alignment_id=alignment.id, label="s1-only", sequence="ACGT", order_index=0
            )
        ],
    )
    remaining = repo.list_alignment_sequences(alignment.id)
    assert [s.label for s in remaining] == ["s1-only"]
    repo.close()
