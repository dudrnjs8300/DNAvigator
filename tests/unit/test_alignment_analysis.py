from genome_workbench.domain.alignment_analysis import (
    consensus_sequence,
    conservation_scores,
    ungapped_range_to_aligned_columns,
)


def test_consensus_sequence_majority_vote():
    seqs = ["ATG-CCGTAA", "ATGACCGTAA", "ATG-CCGTAG"]
    assert consensus_sequence(seqs) == "ATGACCGTAA"


def test_consensus_sequence_ignores_gaps_unless_all_gapped():
    seqs = ["A-", "A-", "--"]
    assert consensus_sequence(seqs) == "A-"


def test_consensus_sequence_ties_break_deterministically():
    # column has one A and one C -- tie, breaks on whichever sorts first
    assert consensus_sequence(["A", "C"]) == "A"
    assert consensus_sequence(["C", "A"]) == "A"


def test_consensus_sequence_empty_input():
    assert consensus_sequence([]) == ""


def test_conservation_scores_fully_conserved_column_scores_one():
    seqs = ["AAA", "AAA", "AAA"]
    assert conservation_scores(seqs) == [1.0, 1.0, 1.0]


def test_conservation_scores_all_gap_column_scores_zero():
    seqs = ["A-", "A-"]
    assert conservation_scores(seqs) == [1.0, 0.0]


def test_conservation_scores_partial_agreement():
    seqs = ["A", "A", "G"]
    assert conservation_scores(seqs) == [2 / 3]


def test_conservation_scores_accepts_precomputed_consensus():
    seqs = ["AAA", "AAA"]
    # deliberately wrong consensus to prove it's used instead of recomputed
    scores = conservation_scores(seqs, consensus="TTT")
    assert scores == [0.0, 0.0, 0.0]


def test_conservation_scores_empty_input():
    assert conservation_scores([]) == []


def test_ungapped_range_maps_directly_when_no_gaps_precede():
    assert ungapped_range_to_aligned_columns("ATGCCGTAA", 0, 3) == (0, 3)


def test_ungapped_range_skips_leading_gaps():
    # this row itself starts with a gap (shorter than the alignment), so its
    # own ungapped position 0 is aligned column 2, not column 0
    assert ungapped_range_to_aligned_columns("--ATGCCGTAA", 0, 3) == (2, 5)


def test_ungapped_range_spans_a_gap_inserted_by_another_row_mid_feature():
    # another sequence's 2bp insertion pads this row with '--' right in the
    # middle of what is, for this row, one contiguous feature
    aligned = "ATG--CCGTAA"
    assert ungapped_range_to_aligned_columns(aligned, 2, 7) == (2, 9)


def test_ungapped_range_whole_sequence():
    aligned = "ATG--CCGTAA"
    assert ungapped_range_to_aligned_columns(aligned, 0, 9) == (0, 11)


def test_ungapped_range_beyond_sequence_end_clamps_to_length():
    aligned = "ATG--CCGTAA"
    assert ungapped_range_to_aligned_columns(aligned, 20, 25) == (11, 11)
