import pytest

from genome_workbench.domain.locations import (
    LocationError,
    LocationPart,
    extract_sequence,
    is_origin_spanning,
    order_parts_for_strand,
    split_origin_spanning,
    total_length,
)


def test_extract_simple_forward():
    seq = "AAAA" + "ATGCCCTAA" + "TTTT"
    parts = [LocationPart(start0=4, end0=13, order_index=0)]
    assert extract_sequence(seq, parts, strand=1) == "ATGCCCTAA"


def test_extract_simple_reverse():
    forward = "ATGCCCTAA"
    rc = "TTAGGGCAT"
    full = "NNN" + rc + "NNN"
    parts = [LocationPart(start0=3, end0=12, order_index=0)]
    assert extract_sequence(full, parts, strand=-1) == forward


def test_extract_join_forward_order_preserved():
    seq = "AAA" + "ATG" + "GG" + "CCC" + "TAA" + "ZZZ"
    # part1 = ATG (3..6), part2 spans GG+CCC+TAA is contiguous here just for simplicity
    part1 = LocationPart(start0=3, end0=6, order_index=0)
    part2 = LocationPart(start0=8, end0=16, order_index=1)
    result = extract_sequence(seq, [part1, part2], strand=1)
    assert result == seq[3:6] + seq[8:16]


def test_extract_join_reverse_rc_each_part_then_concatenate_in_order():
    # Verified against Bio.SeqFeature.CompoundLocation.extract: each part is
    # individually reverse-complemented, then concatenated in order_index
    # order (NOT: concatenate raw parts then RC the whole result).
    seq = "AAACCCGGGTTTAAA"
    part_a = LocationPart(start0=3, end0=6, order_index=0)  # CCC
    part_b = LocationPart(start0=9, end0=12, order_index=1)  # TTT
    from genome_workbench.domain.sequence_ops import reverse_complement

    expected = reverse_complement(seq[3:6]) + reverse_complement(seq[9:12])
    assert extract_sequence(seq, [part_a, part_b], strand=-1) == expected


def test_extract_matches_biopython_reference_for_spliced_minus_strand_gene():
    # Reference behavior captured from Bio.SeqFeature.CompoundLocation.extract:
    # minus-strand compound parts must be stored in descending genomic order
    # (biological 5'->3' order) for correct splicing.
    genome = "TTA" + "N" * 7 + "TTTCAT"  # len 16
    exon1_high_coord = LocationPart(start0=10, end0=16, order_index=0)  # "TTTCAT"
    exon2_low_coord = LocationPart(start0=0, end0=3, order_index=1)  # "TTA"
    result = extract_sequence(genome, [exon1_high_coord, exon2_low_coord], strand=-1)
    assert result == "ATGAAATAA"


def test_extract_requires_at_least_one_part():
    with pytest.raises(LocationError):
        extract_sequence("ACGT", [], strand=1)


def test_total_length():
    parts = [
        LocationPart(start0=0, end0=5, order_index=0),
        LocationPart(start0=10, end0=13, order_index=1),
    ]
    assert total_length(parts) == 8


def test_split_origin_spanning():
    parts = split_origin_spanning(start0=9700, end0=10500, sequence_length=10000)
    assert len(parts) == 2
    assert parts[0].start0 == 9700
    assert parts[0].end0 == 10000
    assert parts[1].start0 == 0
    assert parts[1].end0 == 500


def test_split_no_origin_span_returns_single_part():
    parts = split_origin_spanning(start0=100, end0=900, sequence_length=10000)
    assert len(parts) == 1


def test_is_origin_spanning_detects_split_parts():
    parts = [
        LocationPart(start0=9700, end0=10000, order_index=0),
        LocationPart(start0=0, end0=500, order_index=1),
    ]
    assert is_origin_spanning(parts, sequence_length=10000)


def test_extract_origin_spanning_matches_biological_continuity():
    # circular record: last 4 + first 4 bases spell out a CDS
    seq = "GGGG" + "TTTTTTTT" + "ATGC"  # length 16; feature wraps end->start
    length = len(seq)
    parts = split_origin_spanning(start0=12, end0=length + 4, sequence_length=length)
    result = extract_sequence(seq, parts, strand=1, sequence_length=length)
    assert result == "ATGC" + "GGGG"


def test_order_parts_for_strand_plus_keeps_ascending_order():
    ascending = [
        LocationPart(start0=0, end0=50, order_index=99),
        LocationPart(start0=100, end0=200, order_index=99),
    ]
    ordered = order_parts_for_strand(ascending, strand=1)
    assert [(p.start0, p.end0) for p in ordered] == [(0, 50), (100, 200)]
    assert [p.order_index for p in ordered] == [0, 1]


def test_order_parts_for_strand_minus_reverses_order():
    ascending = [
        LocationPart(start0=0, end0=50, order_index=99),
        LocationPart(start0=100, end0=200, order_index=99),
    ]
    ordered = order_parts_for_strand(ascending, strand=-1)
    assert [(p.start0, p.end0) for p in ordered] == [(100, 200), (0, 50)]
    assert [p.order_index for p in ordered] == [0, 1]


def test_extract_origin_spanning_minus_strand_uses_reversed_biological_order():
    # Footprint: [9700, 10000) union [0, 500) on a length-10000 circular record.
    # split_origin_spanning gives the plus-strand (ascending traversal) order
    # [(9700,10000), (0,500)]; the minus-strand transcript reads this
    # footprint in the opposite direction, so order_index must reverse it.
    length = 10000
    plus_order_parts = split_origin_spanning(start0=9700, end0=length + 500, sequence_length=length)
    assert [(p.start0, p.end0) for p in plus_order_parts] == [(9700, 10000), (0, 500)]
    minus_order_parts = order_parts_for_strand(plus_order_parts, strand=-1)
    assert [(p.start0, p.end0) for p in minus_order_parts] == [(0, 500), (9700, 10000)]
