"""Per-column consensus and conservation math for multiple sequence alignments.

Pure Python, no Qt/Biopython -- unit-testable without a QApplication, same
reasoning as viewport_transform.py.
"""

from __future__ import annotations

from collections import Counter

_GAP_CHARS = frozenset("-.")


def consensus_sequence(sequences: list[str]) -> str:
    """Per-column majority residue, ignoring gaps unless every row is gapped
    at that column (in which case the consensus is a gap too). Ties break on
    whichever residue sorts first, so the result is deterministic.
    """
    if not sequences:
        return ""
    length = len(sequences[0])
    columns = []
    for col in range(length):
        residues = [seq[col].upper() for seq in sequences if seq[col] not in _GAP_CHARS]
        if not residues:
            columns.append("-")
            continue
        counts = Counter(residues)
        best_count = max(counts.values())
        winner = min(r for r, c in counts.items() if c == best_count)
        columns.append(winner)
    return "".join(columns)


def conservation_scores(sequences: list[str], consensus: str | None = None) -> list[float]:
    """Per-column fraction of non-gap rows that match the consensus residue
    at that column -- 1.0 means fully conserved, 0.0 means every row differs.
    A column where every row is a gap scores 0.0 (nothing to conserve).
    """
    if not sequences:
        return []
    consensus = consensus if consensus is not None else consensus_sequence(sequences)
    length = len(sequences[0])
    scores = []
    for col in range(length):
        residues = [seq[col].upper() for seq in sequences if seq[col] not in _GAP_CHARS]
        if not residues:
            scores.append(0.0)
            continue
        matches = sum(1 for r in residues if r == consensus[col])
        scores.append(matches / len(residues))
    return scores
