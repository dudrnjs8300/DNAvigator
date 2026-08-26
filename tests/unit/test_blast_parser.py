from genome_workbench.infrastructure.blast.parser import parse_tabular_output


def _row(**overrides) -> str:
    values = {
        "qseqid": "Q1",
        "sseqid": "S1",
        "pident": "98.5",
        "length": "100",
        "mismatch": "1",
        "gapopen": "0",
        "qstart": "1",
        "qend": "100",
        "sstart": "500",
        "send": "599",
        "evalue": "1e-50",
        "bitscore": "180",
        "qlen": "100",
        "slen": "1000",
        "qcovhsp": "100",
        "nident": "98",
        "positive": "98",
        "gaps": "0",
        "frames": "+1/+1",
        "qseq": "ACGT",
        "sseq": "ACGT",
        "stitle": "Example subject protein",
    }
    values.update(overrides)
    return "\t".join(values.values())


def test_parse_single_hit_forward_strand():
    result = parse_tabular_output(_row())
    assert result.issues == []
    assert len(result.hits) == 1
    hit = result.hits[0]
    assert hit.subject_id == "S1"
    assert hit.subject_title == "Example subject protein"
    hsp = hit.hsps[0]
    assert hsp.subject_strand == 1
    assert hsp.query_start0 == 0
    assert hsp.query_end0 == 100
    assert hsp.subject_start0 == 499
    assert hsp.subject_end0 == 599
    assert hsp.identity_pct == 98.5
    assert hsp.evalue == 1e-50


def test_parse_reverse_strand_subject_swapped_coordinates():
    result = parse_tabular_output(_row(sstart="599", send="500"))
    hsp = result.hits[0].hsps[0]
    assert hsp.subject_strand == -1
    assert hsp.subject_start0 == 499
    assert hsp.subject_end0 == 599


def test_parse_groups_multiple_hsps_under_same_subject():
    text = _row() + "\n" + _row(qstart="200", qend="300")
    result = parse_tabular_output(text)
    assert len(result.hits) == 1
    assert len(result.hits[0].hsps) == 2


def test_parse_multiple_subjects():
    text = _row(sseqid="S1") + "\n" + _row(sseqid="S2")
    result = parse_tabular_output(text)
    assert [h.subject_id for h in result.hits] == ["S1", "S2"]


def test_parse_skips_malformed_short_line():
    text = "not\tenough\tcolumns"
    result = parse_tabular_output(text)
    assert result.hits == []
    assert len(result.issues) == 1


def test_parse_ignores_blank_and_comment_lines():
    text = "# comment\n\n" + _row()
    result = parse_tabular_output(text)
    assert len(result.hits) == 1


def test_parse_handles_non_numeric_gracefully():
    text = _row(pident="not-a-number")
    result = parse_tabular_output(text)
    assert result.hits == []
    assert len(result.issues) == 1
