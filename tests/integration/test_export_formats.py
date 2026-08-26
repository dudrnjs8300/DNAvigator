from pathlib import Path

from genome_workbench.domain.locations import LocationPart
from genome_workbench.domain.models import Feature, MoleculeType, SequenceRecord, Topology
from genome_workbench.domain.qualifiers import QualifierSet
from genome_workbench.infrastructure.formats.export_formats import (
    write_feature_table_csv,
    write_ffn,
    write_nucleotide_fasta,
    write_protein_fasta_from_cds,
    write_protein_fasta_from_records,
)
from genome_workbench.infrastructure.formats.fasta_adapter import read_fasta


def _nucleotide_record() -> SequenceRecord:
    return SequenceRecord(
        display_id="contig1",
        description="test contig",
        molecule_type=MoleculeType.DNA,
        topology=Topology.LINEAR,
        sequence="A" * 100 + "ATGCCCTAA" + "T" * 100,
        checksum_sha256="",
    )


def _cds_feature(record: SequenceRecord) -> Feature:
    return Feature(
        record_id=record.id,
        type="CDS",
        strand=1,
        parts=[LocationPart(start0=100, end0=109, order_index=0)],
        qualifiers=QualifierSet.from_pairs(
            [("gene", "exampleA"), ("locus_tag", "EX_0001"), ("product", "example protein")]
        ),
    )


def test_write_nucleotide_fasta_excludes_protein_records(tmp_path: Path):
    nucl = _nucleotide_record()
    prot = SequenceRecord(
        display_id="prot1", molecule_type=MoleculeType.PROTEIN, sequence="MKV*", checksum_sha256=""
    )
    out_path = tmp_path / "nucl.fasta"
    count = write_nucleotide_fasta([nucl, prot], out_path)
    assert count == 1
    result = read_fasta(out_path)
    assert len(result.records) == 1
    assert result.records[0].display_id == "contig1"
    assert result.records[0].sequence == nucl.sequence


def test_write_protein_fasta_from_records(tmp_path: Path):
    prot = SequenceRecord(
        display_id="prot1",
        molecule_type=MoleculeType.PROTEIN,
        sequence="MKVLATG*",
        checksum_sha256="",
    )
    nucl = _nucleotide_record()
    out_path = tmp_path / "prot.faa"
    count = write_protein_fasta_from_records([nucl, prot], out_path)
    assert count == 1
    result = read_fasta(out_path)
    assert result.records[0].display_id == "prot1"
    assert result.records[0].sequence == "MKVLATG*"


def test_write_protein_fasta_from_cds_translates(tmp_path: Path):
    record = _nucleotide_record()
    feature = _cds_feature(record)
    out_path = tmp_path / "cds_translations.faa"
    count = write_protein_fasta_from_cds([record], {record.id: [feature]}, out_path)
    assert count == 1
    text = out_path.read_text()
    assert "EX_0001" in text
    assert "example protein" in text
    result = read_fasta(out_path)
    assert result.records[0].sequence == "MP"  # ATG CCC TAA -> M P *


def test_write_ffn_extracts_biological_nucleotide(tmp_path: Path):
    record = _nucleotide_record()
    feature = _cds_feature(record)
    out_path = tmp_path / "cds.ffn"
    count = write_ffn([record], {record.id: [feature]}, out_path)
    assert count == 1
    result = read_fasta(out_path)
    assert result.records[0].sequence == "ATGCCCTAA"


def test_write_feature_table_csv(tmp_path: Path):
    record = _nucleotide_record()
    feature = _cds_feature(record)
    out_path = tmp_path / "features.csv"
    count = write_feature_table_csv([record], {record.id: [feature]}, out_path)
    assert count == 1
    text = out_path.read_text()
    lines = text.strip().splitlines()
    assert lines[0].split(",") == [
        "record_id",
        "feature_id",
        "type",
        "start_1based",
        "end_1based",
        "strand",
        "length",
        "gene",
        "locus_tag",
        "product",
        "note",
        "source",
        "provenance_id",
    ]
    row = lines[1].split(",")
    assert row[0] == "contig1"
    assert row[2] == "CDS"
    assert row[3] == "101"
    assert row[4] == "109"
    assert row[5] == "+"
    assert row[7] == "exampleA"
