from pathlib import Path

from genome_workbench.domain.locations import LocationOperator, LocationPart
from genome_workbench.domain.models import Feature, MoleculeType, SequenceRecord, Topology
from genome_workbench.domain.qualifiers import QualifierSet
from genome_workbench.infrastructure.formats.genbank_adapter import (
    read_genbank,
    write_genbank,
)
from genome_workbench.infrastructure.formats.semantic_compare import compare_semantic


def _make_scenario_a_record_and_feature() -> tuple[SequenceRecord, Feature]:
    # AT-01: 101..900 (1-based inclusive) => internal [100, 900)
    cds_span = "ATG" + "CCC" * 265 + "TAA"  # length 800, multiple of 3
    sequence = "A" * 100 + cds_span + "T" * 100  # total length 1000
    record = SequenceRecord(
        display_id="contig1",
        name="contig1",
        description="AT-01 fixture",
        molecule_type=MoleculeType.DNA,
        topology=Topology.LINEAR,
        sequence=sequence,
        checksum_sha256="",
    )
    qualifiers = QualifierSet()
    qualifiers.add("gene", "exampleA")
    qualifiers.add("product", "example protein")
    qualifiers.add("note", "manual test")
    qualifiers.add("transl_table", "11")
    feature = Feature(
        record_id=record.id,
        type="CDS",
        strand=1,
        location_operator=LocationOperator.SIMPLE,
        parts=[LocationPart(start0=100, end0=900, order_index=0)],
        qualifiers=qualifiers,
    )
    return record, feature


def test_at01_fasta_manual_annotation_genbank_round_trip(tmp_path: Path):
    record, feature = _make_scenario_a_record_and_feature()
    out_path = tmp_path / "export.gbk"
    write_genbank([record], {record.id: [feature]}, out_path)

    result = read_genbank(out_path)
    assert len(result.records) == 1
    reimported_record = result.records[0]
    assert reimported_record.sequence == record.sequence
    assert reimported_record.molecule_type == MoleculeType.DNA

    reimported_features = result.features_by_record_id[reimported_record.id]
    assert len(reimported_features) == 1
    rf = reimported_features[0]
    assert rf.type == "CDS"
    assert rf.strand == 1
    assert [(p.start0, p.end0) for p in rf.parts] == [(100, 900)]
    assert rf.qualifiers.get_first("gene") == "exampleA"
    assert rf.qualifiers.get_first("product") == "example protein"
    assert rf.qualifiers.get_first("note") == "manual test"

    diffs = compare_semantic(
        [record],
        {record.id: [feature]},
        [reimported_record],
        {reimported_record.id: reimported_features},
    )
    errors = [d for d in diffs if d.severity == "error"]
    assert errors == []


def test_at02_reverse_strand_cds_round_trip(tmp_path: Path):
    sequence = "N" * 100 + "ATGAAATAA" + "N" * 891  # len 1000
    from genome_workbench.domain.sequence_ops import reverse_complement

    rc_segment = reverse_complement("ATGAAATAA")
    sequence = "N" * 100 + rc_segment + "N" * 891
    record = SequenceRecord(
        display_id="contig_rev",
        molecule_type=MoleculeType.DNA,
        topology=Topology.LINEAR,
        sequence=sequence,
        checksum_sha256="",
    )
    feature = Feature(
        record_id=record.id,
        type="CDS",
        strand=-1,
        parts=[LocationPart(start0=100, end0=109, order_index=0)],
        qualifiers=QualifierSet.from_pairs([("gene", "revgene")]),
    )
    out_path = tmp_path / "reverse.gbk"
    write_genbank([record], {record.id: [feature]}, out_path)

    result = read_genbank(out_path)
    reimported_record = result.records[0]
    reimported_feature = result.features_by_record_id[reimported_record.id][0]
    assert reimported_feature.strand == -1

    from genome_workbench.domain.locations import extract_sequence

    nt = extract_sequence(
        reimported_record.sequence,
        reimported_feature.parts,
        reimported_feature.strand,
        len(reimported_record.sequence),
    )
    assert nt == "ATGAAATAA"


def test_multi_exon_reverse_strand_join_round_trip(tmp_path: Path):
    # Biological mRNA (5'->3'): ATGAAATAA, split into two exons on minus strand.
    # exon1 (5' end, biologically first) sits at the HIGHER genomic coordinate.
    genome = "TTA" + "N" * 7 + "TTTCAT" + "N" * 40  # len 56
    record = SequenceRecord(
        display_id="contig_join",
        molecule_type=MoleculeType.DNA,
        topology=Topology.LINEAR,
        sequence=genome,
        checksum_sha256="",
    )
    exon1_high_coord = LocationPart(start0=10, end0=16, order_index=0)
    exon2_low_coord = LocationPart(start0=0, end0=3, order_index=1)
    feature = Feature(
        record_id=record.id,
        type="CDS",
        strand=-1,
        location_operator=LocationOperator.JOIN,
        parts=[exon1_high_coord, exon2_low_coord],
        qualifiers=QualifierSet.from_pairs([("gene", "joingene")]),
    )
    out_path = tmp_path / "join.gbk"
    write_genbank([record], {record.id: [feature]}, out_path)
    text = out_path.read_text()
    assert "complement(join(1..3,11..16))" in text

    result = read_genbank(out_path)
    reimported_record = result.records[0]
    reimported_feature = result.features_by_record_id[reimported_record.id][0]

    from genome_workbench.domain.locations import extract_sequence

    nt = extract_sequence(
        reimported_record.sequence,
        reimported_feature.parts,
        reimported_feature.strand,
        len(reimported_record.sequence),
    )
    assert nt == "ATGAAATAA"


def test_unknown_qualifiers_preserved(tmp_path: Path):
    record, _ = _make_scenario_a_record_and_feature()
    qualifiers = QualifierSet()
    qualifiers.add("totally_custom_key", "value1")
    qualifiers.add("db_xref", "GO:0001")
    qualifiers.add("db_xref", "GO:0002")
    feature = Feature(
        record_id=record.id,
        type="misc_feature",
        parts=[LocationPart(start0=10, end0=50, order_index=0)],
        qualifiers=qualifiers,
    )
    out_path = tmp_path / "unknown_qual.gbk"
    write_genbank([record], {record.id: [feature]}, out_path)

    result = read_genbank(out_path)
    reimported_feature = result.features_by_record_id[result.records[0].id][0]
    assert reimported_feature.qualifiers.get("totally_custom_key") == ["value1"]
    assert reimported_feature.qualifiers.get("db_xref") == ["GO:0001", "GO:0002"]


def test_circular_topology_preserved(tmp_path: Path):
    record, feature = _make_scenario_a_record_and_feature()
    record.topology = Topology.CIRCULAR
    out_path = tmp_path / "circular.gbk"
    write_genbank([record], {record.id: [feature]}, out_path)
    result = read_genbank(out_path)
    assert result.records[0].topology == Topology.CIRCULAR


def test_multi_record_genbank_import(tmp_path: Path):
    record1, feature1 = _make_scenario_a_record_and_feature()
    record2 = SequenceRecord(
        display_id="contig2",
        molecule_type=MoleculeType.DNA,
        topology=Topology.LINEAR,
        sequence="A" * 500,
        checksum_sha256="",
    )
    out_path = tmp_path / "multi.gbk"
    write_genbank(
        [record1, record2],
        {record1.id: [feature1], record2.id: []},
        out_path,
    )
    result = read_genbank(out_path)
    assert len(result.records) == 2
    assert [r.display_id for r in result.records] == ["contig1", "contig2"]


def test_protein_fasta_style_record_round_trip(tmp_path: Path):
    record = SequenceRecord(
        display_id="protein1",
        molecule_type=MoleculeType.PROTEIN,
        topology=Topology.LINEAR,
        sequence="MKVLATGCDEFGHIKLMNPQRSTVWY",
        checksum_sha256="",
    )
    out_path = tmp_path / "protein.gbk"
    write_genbank([record], {record.id: []}, out_path)
    result = read_genbank(out_path)
    assert result.records[0].molecule_type == MoleculeType.PROTEIN
    assert result.records[0].sequence == "MKVLATGCDEFGHIKLMNPQRSTVWY"
