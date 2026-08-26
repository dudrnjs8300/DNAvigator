"""Phase 2 gate: every fixture in spec 16.2 must import without crashing.
Malformed fixtures must produce reported issues, not exceptions.
"""

from pathlib import Path

import pytest

from genome_workbench.domain.locations import extract_sequence, split_origin_spanning
from genome_workbench.infrastructure.formats.fasta_adapter import read_fasta
from genome_workbench.infrastructure.formats.genbank_adapter import read_genbank
from genome_workbench.infrastructure.formats.gff3_adapter import read_gff3

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


def test_simple_linear_fasta():
    result = read_fasta(FIXTURES_DIR / "simple_linear.fasta")
    assert len(result.records) == 1
    assert result.records[0].length == 1000


def test_multi_contig_fasta_reports_duplicate_id():
    result = read_fasta(FIXTURES_DIR / "multi_contig.fasta")
    assert len(result.records) == 4
    assert any(issue.code == "duplicate_record_id" for issue in result.issues)


def test_protein_set_faa():
    from genome_workbench.domain.models import MoleculeType

    result = read_fasta(FIXTURES_DIR / "protein_set.faa")
    assert len(result.records) == 3
    assert all(r.molecule_type == MoleculeType.PROTEIN for r in result.records)


def test_annotated_linear_gbk_full_import():
    result = read_genbank(FIXTURES_DIR / "annotated_linear.gbk")
    assert result.issues == []
    record = result.records[0]
    features = result.features_by_record_id[record.id]
    types = {f.type for f in features}
    assert {"source", "gene", "CDS", "tRNA", "rRNA"} <= types
    strands = {f.strand for f in features if f.type == "CDS"}
    assert strands == {1, -1}


def test_circular_origin_gbk_extraction_matches_source():
    result = read_genbank(FIXTURES_DIR / "circular_origin.gbk")
    assert result.issues == []
    record = result.records[0]
    feature = result.features_by_record_id[record.id][0]
    assert len(feature.parts) == 2
    nt = extract_sequence(record.sequence, feature.parts, feature.strand, record.length)
    # re-derive the same extraction from the fixture generator's own logic as a cross-check
    expected_parts = split_origin_spanning(
        start0=record.length - 300, end0=record.length + 500, sequence_length=record.length
    )
    expected_nt = extract_sequence(record.sequence, expected_parts, 1, record.length)
    assert nt == expected_nt


def test_compound_fuzzy_gbk_preserves_join_and_fuzzy():
    result = read_genbank(FIXTURES_DIR / "compound_fuzzy.gbk")
    assert result.issues == []
    record = result.records[0]
    features = result.features_by_record_id[record.id]
    join_feature = next(f for f in features if len(f.parts) > 1)
    assert join_feature.strand == -1
    fuzzy_feature = next(f for f in features if f.type == "misc_feature")
    assert fuzzy_feature.parts[0].fuzzy_start
    assert fuzzy_feature.parts[0].fuzzy_end


def test_annotated_embedded_gff3_parent_chain():
    result = read_gff3(FIXTURES_DIR / "annotated_embedded.gff3")
    assert result.issues == []
    record = result.records[0]
    assert record.sequence  # embedded FASTA was parsed
    features = result.features_by_record_id[record.id]
    by_type = {f.type: f for f in features}
    assert by_type["CDS"].parent_ids == [by_type["mRNA"].id]
    assert by_type["mRNA"].parent_ids == [by_type["gene"].id]


def test_annotation_only_gff3_reports_unmatched_seqid():
    result = read_gff3(FIXTURES_DIR / "annotation_only.gff3")
    assert "annotation_only_contig" in result.unmatched_seqids


def test_annotation_only_gff3_pairs_with_matching_fna():
    from genome_workbench.application.import_service import ImportService
    from genome_workbench.application.project_service import ProjectService

    project_service = ProjectService()
    project_service.create_new(FIXTURES_DIR.parent / "tmp_pairing_test.gwbproj", "tmp")
    try:
        import_service = ImportService(project_service)
        result = import_service.import_gff3(
            FIXTURES_DIR / "annotation_only.gff3",
            external_fasta_path=FIXTURES_DIR / "matching.fna",
        )
        assert result.records[0].sequence
        assert not any(issue.code == "unmatched_seqid" for issue in result.issues)
    finally:
        project_service.close()
        (FIXTURES_DIR.parent / "tmp_pairing_test.gwbproj").unlink(missing_ok=True)


def test_invalid_coordinates_gff3_reports_issues_without_crashing():
    result = read_gff3(FIXTURES_DIR / "invalid_coordinates.gff3")
    assert result.issues  # must be reported, not silently dropped or crashed
    record = result.records[0]
    features = result.features_by_record_id[record.id]
    # the one well-formed feature must still import despite the two bad ones
    assert any(f.type == "misc_feature" for f in features)


def test_duplicate_ids_fasta_both_kept_with_warning():
    result = read_fasta(FIXTURES_DIR / "duplicate_ids.fasta")
    assert len(result.records) == 2
    assert any(issue.code == "duplicate_record_id" for issue in result.issues)


def test_unicode_path_gbk_import():
    path = FIXTURES_DIR / "unicode_경로 테스트" / "균주 A.gbk"
    assert path.exists()
    result = read_genbank(path)
    assert result.issues == []
    assert result.records[0].display_id == "strain_A"


def test_tiny_blast_fixtures_readable():
    from genome_workbench.domain.models import MoleculeType

    nucl = read_fasta(FIXTURES_DIR / "tiny_nucleotide_db.fasta")
    assert len(nucl.records) == 2
    prot = read_fasta(FIXTURES_DIR / "tiny_protein_db.faa")
    assert len(prot.records) == 2
    assert all(r.molecule_type == MoleculeType.PROTEIN for r in prot.records)


@pytest.mark.parametrize(
    "filename",
    [
        "simple_linear.fasta",
        "multi_contig.fasta",
        "protein_set.faa",
        "annotated_linear.gbk",
        "circular_origin.gbk",
        "compound_fuzzy.gbk",
        "annotated_embedded.gff3",
        "annotation_only.gff3",
        "matching.fna",
        "invalid_coordinates.gff3",
        "duplicate_ids.fasta",
        "tiny_nucleotide_db.fasta",
        "tiny_protein_db.faa",
    ],
)
def test_all_fixtures_exist(filename: str):
    assert (FIXTURES_DIR / filename).exists()
