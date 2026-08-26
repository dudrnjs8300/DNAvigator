from hypothesis import given
from hypothesis import strategies as st

from genome_workbench.domain.sequence_ops import (
    gc_content,
    reverse_complement,
    translate,
)

dna_strategy = st.text(alphabet="ACGT", min_size=0, max_size=200)


def test_reverse_complement_basic():
    assert reverse_complement("ATGC") == "GCAT"


def test_reverse_complement_ambiguous():
    assert reverse_complement("ATGN") == "NCAT"


@given(dna_strategy)
def test_reverse_complement_involution(seq):
    assert reverse_complement(reverse_complement(seq)) == seq


def test_gc_content_all_gc():
    assert gc_content("GCGC") == 1.0


def test_gc_content_none():
    assert gc_content("ATAT") == 0.0


def test_gc_content_empty():
    assert gc_content("") == 0.0


def test_translate_example_start_stop():
    # ATG (M/start) CCC (P) TAA (stop)
    result = translate("ATGCCCTAA", genetic_code=11)
    assert result.protein == "MP"
    assert result.has_start_codon
    assert result.has_stop_codon
    assert result.internal_stop_count == 0
    assert result.is_multiple_of_three


def test_translate_internal_stop_detected():
    result = translate("ATGTAACCC", genetic_code=11)
    assert result.internal_stop_count == 1


def test_translate_codon_start_offset():
    # shifting by 1 changes the reading frame
    result = translate("AATGCCCTAA", genetic_code=11, codon_start_offset=1)
    assert result.protein == "MP"


def test_translate_alternative_bacterial_start_gtg():
    result = translate("GTGCCCTAA", genetic_code=11)
    assert result.has_start_codon
