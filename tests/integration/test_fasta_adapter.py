from pathlib import Path

from genome_workbench.domain.models import MoleculeType
from genome_workbench.infrastructure.formats.fasta_adapter import (
    guess_molecule_type,
    read_fasta,
)


def test_guess_molecule_type_dna():
    assert guess_molecule_type("ACGTACGTNNNN") == MoleculeType.DNA


def test_guess_molecule_type_rna():
    assert guess_molecule_type("ACGUACGU") == MoleculeType.RNA


def test_guess_molecule_type_protein():
    assert guess_molecule_type("MKVLATG*") == MoleculeType.PROTEIN


def test_read_simple_fasta(tmp_path: Path):
    fasta = tmp_path / "simple.fasta"
    fasta.write_text(">seq1 description here\nACGTACGTACGTACGT\n>seq2\nMKVLQ\n")
    result = read_fasta(fasta)
    assert len(result.records) == 2
    assert result.records[0].display_id == "seq1"
    assert result.records[0].description.startswith("seq1")
    assert result.records[0].molecule_type == MoleculeType.DNA
    assert result.records[1].molecule_type == MoleculeType.PROTEIN


def test_read_fasta_reports_duplicate_ids(tmp_path: Path):
    fasta = tmp_path / "dup.fasta"
    fasta.write_text(">a\nACGT\n>a\nTTTT\n")
    result = read_fasta(fasta)
    assert len(result.records) == 2
    assert any(issue.code == "duplicate_record_id" for issue in result.issues)


def test_read_fasta_zero_length_record_skipped(tmp_path: Path):
    fasta = tmp_path / "zero.fasta"
    fasta.write_text(">empty\n\n>real\nACGT\n")
    result = read_fasta(fasta)
    assert len(result.records) == 1
    assert result.records[0].display_id == "real"
    assert any(issue.code == "zero_length_record" for issue in result.issues)


def test_read_fasta_gzip(tmp_path: Path):
    import gzip

    fasta = tmp_path / "compressed.fasta.gz"
    with gzip.open(fasta, "wt") as handle:
        handle.write(">seq1\nACGTACGT\n")
    result = read_fasta(fasta)
    assert len(result.records) == 1
    assert result.records[0].sequence == "ACGTACGT"


def test_read_fasta_korean_path(tmp_path: Path):
    directory = tmp_path / "균주 A 데이터"
    directory.mkdir()
    fasta = directory / "샘플.fasta"
    fasta.write_text(">seq1\nACGTACGT\n", encoding="utf-8")
    result = read_fasta(fasta)
    assert len(result.records) == 1
