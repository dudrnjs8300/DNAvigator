from genome_workbench.domain.blast_models import (
    BlastHsp,
    BlastProgram,
    BlastSearchParameters,
    BlastSearchResult,
    map_hsp_to_genome_location,
)


def _hsp(query_start0: int, query_end0: int, subject_strand: int = 1) -> BlastHsp:
    return BlastHsp(
        query_start0=query_start0,
        query_end0=query_end0,
        subject_start0=0,
        subject_end0=10,
        subject_strand=subject_strand,
        identity_pct=100.0,
        align_length=query_end0 - query_start0,
        mismatches=0,
        gap_opens=0,
        evalue=1e-10,
        bitscore=50.0,
        query_length=100,
        subject_length=100,
        query_coverage_pct=100.0,
        query_seq="A",
        subject_seq="A",
    )


def _result(
    query_source_start0: int, query_source_end0: int, query_source_strand: int
) -> BlastSearchResult:
    return BlastSearchResult(
        program=BlastProgram.BLASTN,
        database_id="db1",
        query_checksum="x",
        parameters=BlastSearchParameters(program=BlastProgram.BLASTN),
        query_source_record_id="rec1",
        query_source_start0=query_source_start0,
        query_source_end0=query_source_end0,
        query_source_strand=query_source_strand,
    )


def test_plus_strand_query_plus_strand_subject():
    result = _result(1000, 1100, query_source_strand=1)
    hsp = _hsp(10, 50, subject_strand=1)
    start0, end0, strand = map_hsp_to_genome_location(result, hsp)
    assert (start0, end0, strand) == (1010, 1050, 1)


def test_plus_strand_query_minus_strand_subject():
    result = _result(1000, 1100, query_source_strand=1)
    hsp = _hsp(10, 50, subject_strand=-1)
    start0, end0, strand = map_hsp_to_genome_location(result, hsp)
    assert (start0, end0, strand) == (1010, 1050, -1)


def test_minus_strand_query_plus_strand_subject_mirrors_offset():
    # query was the reverse-complement of genome[1000:1100); hsp query_start0=10
    # means "10 bases into the RC'd query", which is the region just before
    # genome position 1090 (i.e. genome[1050:1090)).
    result = _result(1000, 1100, query_source_strand=-1)
    hsp = _hsp(10, 50, subject_strand=1)
    start0, end0, strand = map_hsp_to_genome_location(result, hsp)
    assert (start0, end0, strand) == (1050, 1090, -1)


def test_minus_strand_query_minus_strand_subject_double_reversal_cancels():
    result = _result(1000, 1100, query_source_strand=-1)
    hsp = _hsp(10, 50, subject_strand=-1)
    start0, end0, strand = map_hsp_to_genome_location(result, hsp)
    assert (start0, end0, strand) == (1050, 1090, 1)
