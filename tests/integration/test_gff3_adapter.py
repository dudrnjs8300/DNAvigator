from pathlib import Path

from genome_workbench.domain.locations import LocationOperator, LocationPart, extract_sequence
from genome_workbench.domain.models import Feature, MoleculeType, SequenceRecord, Topology
from genome_workbench.domain.qualifiers import QualifierSet
from genome_workbench.infrastructure.formats.gff3_adapter import read_gff3, write_gff3


def _record(seq: str, display_id: str = "contig1") -> SequenceRecord:
    return SequenceRecord(
        display_id=display_id,
        molecule_type=MoleculeType.DNA,
        topology=Topology.LINEAR,
        sequence=seq,
        checksum_sha256="",
    )


def test_simple_feature_round_trip(tmp_path: Path):
    record = _record("A" * 100 + "ATGCCCTAA" + "T" * 100)
    qualifiers = QualifierSet.from_pairs([("gene", "exampleA"), ("product", "example protein")])
    feature = Feature(
        record_id=record.id,
        type="CDS",
        strand=1,
        parts=[LocationPart(start0=100, end0=109, order_index=0)],
        qualifiers=qualifiers,
    )
    out_path = tmp_path / "simple.gff3"
    write_gff3([record], {record.id: [feature]}, out_path)

    text = out_path.read_text()
    assert text.startswith("##gff-version 3")
    assert "\tCDS\t101\t109\t" in text

    result = read_gff3(out_path)
    assert result.issues == []
    reimported_record = result.records[0]
    assert reimported_record.sequence == record.sequence
    reimported_feature = result.features_by_record_id[reimported_record.id][0]
    assert reimported_feature.type == "CDS"
    assert reimported_feature.strand == 1
    assert [(p.start0, p.end0) for p in reimported_feature.parts] == [(100, 109)]
    assert reimported_feature.qualifiers.get_first("gene") == "exampleA"
    assert reimported_feature.qualifiers.get_first("product") == "example protein"


def test_rejects_file_without_gff_version_header(tmp_path: Path):
    path = tmp_path / "not_gff3.gff"
    path.write_text("contig1\t.\tgene\t1\t10\t.\t+\t.\tID=g1\n")
    result = read_gff3(path)
    assert any(issue.code == "not_gff3" for issue in result.issues)
    assert result.records == []


def test_multi_exon_reverse_strand_discontinuous_feature_matches_biological_order(tmp_path: Path):
    # Same biological scenario as the GenBank D-002 regression test: mRNA
    # ATGAAATAA split across two exons on the minus strand.
    genome = "TTA" + "N" * 7 + "TTTCAT" + "N" * 40  # len 56

    out_path = tmp_path / "join.gff3"
    lines = [
        "##gff-version 3",
        f"##sequence-region contig_join 1 {len(genome)}",
        "contig_join\t.\tCDS\t1\t3\t.\t-\t.\tID=cds1;gene=joingene",
        "contig_join\t.\tCDS\t11\t16\t.\t-\t.\tID=cds1;gene=joingene",
        "##FASTA",
        ">contig_join",
        genome,
    ]
    out_path.write_text("\n".join(lines) + "\n")

    result = read_gff3(out_path)
    assert result.issues == []
    reimported_record = result.records[0]
    feature = result.features_by_record_id[reimported_record.id][0]
    assert feature.location_operator == LocationOperator.JOIN
    # order_index must reflect descending genomic order (biological order) for minus strand
    assert [(p.start0, p.end0) for p in feature.parts] == [(10, 16), (0, 3)]

    nt = extract_sequence(
        reimported_record.sequence, feature.parts, feature.strand, len(reimported_record.sequence)
    )
    assert nt == "ATGAAATAA"


def test_write_then_reread_preserves_compound_reverse_strand_extraction(tmp_path: Path):
    genome = "TTA" + "N" * 7 + "TTTCAT" + "N" * 40
    record = _record(genome, display_id="contig_join2")
    feature = Feature(
        record_id=record.id,
        type="CDS",
        strand=-1,
        location_operator=LocationOperator.JOIN,
        parts=[
            LocationPart(start0=10, end0=16, order_index=0),
            LocationPart(start0=0, end0=3, order_index=1),
        ],
        qualifiers=QualifierSet.from_pairs([("gene", "joingene2")]),
    )
    out_path = tmp_path / "roundtrip_join.gff3"
    write_gff3([record], {record.id: [feature]}, out_path)

    text = out_path.read_text()
    # exported lines must be in ascending genomic order (GFF3 convention)
    cds_lines = [line for line in text.splitlines() if "\tCDS\t" in line]
    assert len(cds_lines) == 2
    assert cds_lines[0].split("\t")[3] == "1"
    assert cds_lines[1].split("\t")[3] == "11"

    result = read_gff3(out_path)
    reimported_feature = result.features_by_record_id[result.records[0].id][0]
    nt = extract_sequence(
        result.records[0].sequence,
        reimported_feature.parts,
        reimported_feature.strand,
        len(result.records[0].sequence),
    )
    assert nt == "ATGAAATAA"


def test_parent_child_relationship_preserved(tmp_path: Path):
    out_path = tmp_path / "parent_child.gff3"
    lines = [
        "##gff-version 3",
        "##sequence-region contig1 1 200",
        "contig1\t.\tgene\t1\t100\t.\t+\t.\tID=gene1;Name=exampleGene",
        "contig1\t.\tmRNA\t1\t100\t.\t+\t.\tID=mrna1;Parent=gene1",
        "contig1\t.\tCDS\t1\t100\t.\t+\t0\tID=cds1;Parent=mrna1",
    ]
    out_path.write_text("\n".join(lines) + "\n")

    result = read_gff3(out_path)
    features = result.features_by_record_id[result.records[0].id]
    by_type = {f.type: f for f in features}
    assert by_type["mRNA"].parent_ids == [by_type["gene"].id]
    assert by_type["CDS"].parent_ids == [by_type["mRNA"].id]
    assert by_type["mRNA"].id in by_type["gene"].child_ids
    assert by_type["gene"].qualifiers.get_first("Name") == "exampleGene"


def test_parent_cycle_reported_as_error(tmp_path: Path):
    out_path = tmp_path / "cycle.gff3"
    lines = [
        "##gff-version 3",
        "##sequence-region contig1 1 200",
        "contig1\t.\tgene\t1\t100\t.\t+\t.\tID=a;Parent=b",
        "contig1\t.\tgene\t1\t100\t.\t+\t.\tID=b;Parent=a",
    ]
    out_path.write_text("\n".join(lines) + "\n")
    result = read_gff3(out_path)
    assert any(issue.code == "parent_cycle" for issue in result.issues)


def test_percent_escaping_round_trip(tmp_path: Path):
    record = _record("A" * 100)
    qualifiers = QualifierSet.from_pairs([("note", "contains;semicolon,and=equals")])
    feature = Feature(
        record_id=record.id,
        type="misc_feature",
        strand=1,
        parts=[LocationPart(start0=10, end0=50, order_index=0)],
        qualifiers=qualifiers,
    )
    out_path = tmp_path / "escaped.gff3"
    write_gff3([record], {record.id: [feature]}, out_path)
    result = read_gff3(out_path)
    reimported = result.features_by_record_id[result.records[0].id][0]
    assert reimported.qualifiers.get_first("note") == "contains;semicolon,and=equals"


def test_unmatched_seqid_reported_when_no_sequence_available(tmp_path: Path):
    out_path = tmp_path / "annotation_only.gff3"
    lines = [
        "##gff-version 3",
        "contig_missing\t.\tgene\t1\t100\t.\t+\t.\tID=g1",
    ]
    out_path.write_text("\n".join(lines) + "\n")
    result = read_gff3(out_path)
    assert "contig_missing" in result.unmatched_seqids


def test_cds_phase_preserved(tmp_path: Path):
    record = _record("A" * 100 + "ATGCCCTAA" + "T" * 100)
    feature = Feature(
        record_id=record.id,
        type="CDS",
        strand=1,
        parts=[LocationPart(start0=100, end0=109, order_index=0, phase=0)],
        qualifiers=QualifierSet(),
        phase=0,
    )
    out_path = tmp_path / "phase.gff3"
    write_gff3([record], {record.id: [feature]}, out_path)
    text = out_path.read_text()
    cds_line = next(line for line in text.splitlines() if "\tCDS\t" in line)
    assert cds_line.split("\t")[7] == "0"

    result = read_gff3(out_path)
    reimported = result.features_by_record_id[result.records[0].id][0]
    assert reimported.parts[0].phase == 0
