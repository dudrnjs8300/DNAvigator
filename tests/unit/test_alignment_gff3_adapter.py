from pathlib import Path

from genome_workbench.domain.models import AlignmentSequence
from genome_workbench.infrastructure.formats.alignment_gff3_adapter import read_alignment_gff3

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


def _sequences() -> list[AlignmentSequence]:
    return [
        AlignmentSequence(alignment_id="a1", label="isolate1", sequence="ATG-CCGTAA"),
        AlignmentSequence(alignment_id="a1", label="isolate2", sequence="ATGACCGTAA"),
    ]


def test_matches_features_to_sequences_by_gff_seqid():
    sequences = _sequences()
    result = read_alignment_gff3(FIXTURES_DIR / "alignment_annotations.gff3", sequences)
    types_by_seqid = sorted((f.alignment_sequence_id, f.type) for f in result.features)
    seq_ids = {s.label: s.id for s in sequences}
    assert types_by_seqid == sorted(
        [
            (seq_ids["isolate1"], "gene"),
            (seq_ids["isolate1"], "CDS"),
            (seq_ids["isolate2"], "gene"),
        ]
    )


def test_coordinates_are_0based_ungapped_on_that_row():
    result = read_alignment_gff3(FIXTURES_DIR / "alignment_annotations.gff3", _sequences())
    gene = next(f for f in result.features if f.type == "gene" and f.strand == 1)
    assert (gene.start0, gene.end0) == (2, 8)  # GFF3 3..8 (1-based) -> 2..8 (0-based)


def test_strand_and_qualifiers_are_parsed():
    result = read_alignment_gff3(FIXTURES_DIR / "alignment_annotations.gff3", _sequences())
    gene = next(f for f in result.features if f.qualifiers.get_first("gene") == "blaTEM-1")
    assert gene.strand == 1
    assert gene.qualifiers.get_first("product") == "beta-lactamase"

    recA = next(f for f in result.features if f.qualifiers.get_first("gene") == "recA")
    assert recA.strand == -1


def test_unmatched_seqid_is_reported_and_skipped():
    result = read_alignment_gff3(FIXTURES_DIR / "alignment_annotations.gff3", _sequences())
    assert result.unmatched_seqids == {"not_in_alignment"}
    assert any(i.code == "unmatched_seqid" for i in result.issues)
    assert not any(f.type == "gene" and f.strand == 1 and f.start0 == 0 for f in result.features)


def test_ignores_id_parent_grouping_every_line_is_its_own_feature():
    result = read_alignment_gff3(FIXTURES_DIR / "alignment_annotations.gff3", _sequences())
    isolate1_features = [f for f in result.features if f.qualifiers.get_first("product")]
    assert len(isolate1_features) == 2  # gene line + CDS line, not merged


def test_non_gff3_file_reports_error(tmp_path: Path):
    junk = tmp_path / "not_gff.txt"
    junk.write_text("this is not gff3\n")
    result = read_alignment_gff3(junk, _sequences())
    assert result.features == []
    assert any(i.code == "not_gff3" for i in result.issues)


def test_malformed_line_is_reported_but_does_not_stop_parsing(tmp_path: Path):
    path = tmp_path / "bad.gff3"
    path.write_text(
        "##gff-version 3\n"
        "isolate1\tprokka\tgene\ttoo\tfew\tcolumns\n"
        "isolate1\tprokka\tgene\t1\t5\t.\t+\t.\tID=g1\n"
    )
    result = read_alignment_gff3(path, _sequences())
    assert any(i.code == "malformed_line" for i in result.issues)
    assert len(result.features) == 1
