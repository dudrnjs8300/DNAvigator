from pathlib import Path

from genome_workbench.domain.models import MoleculeType
from genome_workbench.infrastructure.formats.alignment_adapter import read_alignment

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


def test_read_fasta_alignment():
    result = read_alignment(FIXTURES_DIR / "sample_alignment.fasta")
    assert not any(i.severity == "error" for i in result.issues)
    assert len(result.alignments) == 1
    alignment = result.alignments[0]
    assert alignment.name == "sample_alignment"
    assert alignment.length == 13
    assert alignment.molecule_type == MoleculeType.DNA
    sequences = result.sequences_by_alignment_id[alignment.id]
    assert [s.label for s in sequences] == ["seqA", "seqB", "seqC"]
    assert sequences[0].sequence == "ATG-CCGTAAGGT"
    assert all(s.alignment_id == alignment.id for s in sequences)
    assert [s.order_index for s in sequences] == [0, 1, 2]


def test_read_clustal_alignment_by_extension():
    result = read_alignment(FIXTURES_DIR / "sample_alignment.aln")
    assert not any(i.severity == "error" for i in result.issues)
    assert len(result.alignments) == 1
    alignment = result.alignments[0]
    sequences = result.sequences_by_alignment_id[alignment.id]
    assert [s.sequence for s in sequences] == [
        "ATG-CCGTAAGGT",
        "ATGACCGTAAGGT",
        "ATG-CCGTAAGGA",
    ]


def test_read_alignment_unrecognized_content_reports_error(tmp_path: Path):
    junk = tmp_path / "not_an_alignment.aln"
    junk.write_text("this is not any alignment format at all\njust some prose.\n")
    result = read_alignment(junk)
    assert result.alignments == []
    assert any(i.code == "unrecognized_alignment_format" for i in result.issues)


def test_read_alignment_single_sequence_warns(tmp_path: Path):
    single = tmp_path / "single.fasta"
    single.write_text(">only\nACGT\n")
    result = read_alignment(single)
    assert len(result.alignments) == 1
    assert any(i.code == "single_sequence_alignment" for i in result.issues)


def test_read_alignment_duplicate_labels_warns(tmp_path: Path):
    dup = tmp_path / "dup.fasta"
    dup.write_text(">seq1\nACGT\n>seq1\nACGA\n")
    result = read_alignment(dup)
    assert len(result.alignments) == 1
    sequences = result.sequences_by_alignment_id[result.alignments[0].id]
    assert [s.label for s in sequences] == ["seq1", "seq1"]
    assert any(i.code == "duplicate_sequence_label" for i in result.issues)


def test_read_alignment_protein_molecule_type_guess(tmp_path: Path):
    protein = tmp_path / "protein.fasta"
    protein.write_text(">p1\nMKV-LWQRST\n>p2\nMKVWLWQRST\n")
    result = read_alignment(protein)
    assert result.alignments[0].molecule_type == MoleculeType.PROTEIN
