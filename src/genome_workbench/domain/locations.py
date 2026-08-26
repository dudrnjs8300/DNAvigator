"""Compound feature locations: ordered parts, strand, and circular origin spans.

Extraction rule (verified against Biopython's ``CompoundLocation.extract``,
which is the reference implementation for GenBank ``complement(join(...))``
semantics): each part is extracted and, if the feature strand is -1,
individually reverse-complemented *before* concatenation; parts are then
concatenated in stored ``order_index`` order with no further reversal.

This is *not* the same as reverse-complementing the whole concatenation as a
single unit — the two only agree when a compound feature's parts are
contiguous. For a genuinely spliced (gapped) reverse-strand feature they
differ, and ``order_index`` for reverse-strand compound features must already
be in biological 5'->3' order (which is the *descending* genomic-coordinate
order for a normal multi-exon minus-strand gene, and the origin-wrap-reversed
order for a circular origin-spanning minus-strand feature). Import adapters
preserve whatever order the source file encodes; :func:`order_parts_for_strand`
computes the correct order_index when building compound locations
programmatically (manual creation, BLAST-derived features) from parts given
in plain ascending genomic order.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from genome_workbench.domain.coordinates import CoordinateError, Interval0
from genome_workbench.domain.sequence_ops import reverse_complement


class LocationOperator(str, Enum):
    SIMPLE = "simple"
    JOIN = "join"
    ORDER = "order"


class LocationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class LocationPart:
    start0: int
    end0: int
    order_index: int
    fuzzy_start: bool = False
    fuzzy_end: bool = False
    phase: int | None = None

    def __post_init__(self) -> None:
        Interval0(self.start0, self.end0)  # validates start0 <= end0, start0 >= 0

    @property
    def length(self) -> int:
        return self.end0 - self.start0

    @property
    def interval(self) -> Interval0:
        return Interval0(self.start0, self.end0)


def sorted_parts(parts: list[LocationPart]) -> list[LocationPart]:
    return sorted(parts, key=lambda p: p.order_index)


def extract_sequence(
    full_sequence: str,
    parts: list[LocationPart],
    strand: int | None,
    sequence_length: int | None = None,
) -> str:
    """Extract the biological sequence for a (possibly compound) location.

    ``full_sequence`` must be the complete record sequence (0-based indexing
    matches ``full_sequence[start0:end0]``). For circular records, a part's
    ``end0`` may exceed ``sequence_length`` is NOT used here — origin-spanning
    features must already be split into parts with in-bounds coordinates by
    the caller (see :mod:`genome_workbench.domain.circular`).
    """
    if not parts:
        raise LocationError("feature must have at least one location part")

    ordered = sorted_parts(parts)
    record_length = sequence_length if sequence_length is not None else len(full_sequence)

    chunks: list[str] = []
    for part in ordered:
        if part.end0 > record_length:
            raise CoordinateError(
                f"location part end0={part.end0} exceeds sequence length {record_length}"
            )
        chunk = full_sequence[part.start0 : part.end0]
        if strand == -1:
            chunk = reverse_complement(chunk)
        chunks.append(chunk)
    return "".join(chunks)


def total_length(parts: list[LocationPart]) -> int:
    return sum(p.length for p in parts)


def normalize_order_indices(parts: list[LocationPart]) -> list[LocationPart]:
    """Re-number order_index 0..n-1 preserving relative order."""
    ordered = sorted_parts(parts)
    return [
        LocationPart(
            start0=p.start0,
            end0=p.end0,
            order_index=i,
            fuzzy_start=p.fuzzy_start,
            fuzzy_end=p.fuzzy_end,
            phase=p.phase,
        )
        for i, p in enumerate(ordered)
    ]


def order_parts_for_strand(
    parts_in_ascending_genomic_order: list[LocationPart], strand: int | None
) -> list[LocationPart]:
    """Assign order_index for a compound feature built from plain genomic parts.

    ``parts_in_ascending_genomic_order`` must already be in ascending
    traversal order (the order produced by a plain footprint split such as
    :func:`split_origin_spanning`, which for circular features is "ascending
    with wraparound" rather than a raw numeric sort by start0). For strand
    +1/None, biological 5'->3' order matches that input order. For strand -1,
    biological order is the reverse (see module docstring).
    """
    ordered = (
        list(reversed(parts_in_ascending_genomic_order))
        if strand == -1
        else list(parts_in_ascending_genomic_order)
    )
    return [
        LocationPart(
            start0=p.start0,
            end0=p.end0,
            order_index=i,
            fuzzy_start=p.fuzzy_start,
            fuzzy_end=p.fuzzy_end,
            phase=p.phase,
        )
        for i, p in enumerate(ordered)
    ]


def split_origin_spanning(start0: int, end0: int, sequence_length: int) -> list[LocationPart]:
    """Split a feature whose end0 exceeds sequence_length (origin-spanning) into parts.

    Input uses an "extended" coordinate space where a feature crossing the
    origin has ``end0 > sequence_length``. Returns parts in ascending
    genomic/traversal order (the plus-strand order_index convention), each
    within ``[0, sequence_length)``. For a minus-strand origin-spanning
    feature, pass the result through :func:`order_parts_for_strand` with
    ``strand=-1`` to get the correct biological order_index.
    """
    if sequence_length <= 0:
        raise CoordinateError("sequence_length must be positive")
    if start0 < 0:
        raise CoordinateError("start0 must be >= 0")
    if end0 <= sequence_length:
        return [LocationPart(start0=start0, end0=end0, order_index=0)]
    if start0 >= sequence_length:
        raise CoordinateError("start0 must be within [0, sequence_length) to split")
    return [
        LocationPart(start0=start0, end0=sequence_length, order_index=0),
        LocationPart(start0=0, end0=end0 - sequence_length, order_index=1),
    ]


def is_origin_spanning(parts: list[LocationPart], sequence_length: int) -> bool:
    """Heuristic: two parts where the first touches the end and the second starts at 0."""
    ordered = sorted_parts(parts)
    if len(ordered) < 2:
        return False
    first, second = ordered[0], ordered[1]
    return first.end0 == sequence_length and second.start0 == 0
