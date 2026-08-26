"""Canonical coordinate conversions.

Internal representation is always 0-based, end-exclusive: ``[start0, end0)``.
UI, GenBank, and GFF3 all use 1-based inclusive coordinates and must convert
at the adapter/UI boundary. Never store or compare 1-based coordinates
internally.
"""

from __future__ import annotations

from dataclasses import dataclass


class CoordinateError(ValueError):
    """Raised when a coordinate pair is not a valid interval."""


@dataclass(frozen=True, slots=True)
class Interval0:
    """A 0-based, end-exclusive half-open interval ``[start0, end0)``."""

    start0: int
    end0: int

    def __post_init__(self) -> None:
        if self.start0 < 0:
            raise CoordinateError(f"start0 must be >= 0, got {self.start0}")
        if self.end0 < self.start0:
            raise CoordinateError(f"end0 ({self.end0}) must be >= start0 ({self.start0})")

    @property
    def length(self) -> int:
        return self.end0 - self.start0

    def to_display(self) -> tuple[int, int]:
        """Return (start_1based_inclusive, end_1based_inclusive)."""
        return display_from_internal(self.start0, self.end0)

    def overlaps(self, other: Interval0) -> bool:
        return self.start0 < other.end0 and other.start0 < self.end0

    def contains_point0(self, point0: int) -> bool:
        return self.start0 <= point0 < self.end0

    @classmethod
    def from_display(cls, start_1based: int, end_1based: int) -> Interval0:
        start0, end0 = internal_from_display(start_1based, end_1based)
        return cls(start0, end0)


def internal_from_display(start_1based: int, end_1based: int) -> tuple[int, int]:
    """Convert UI/GenBank/GFF3 1-based inclusive coordinates to internal 0-based half-open.

    ``101..900`` (1-based inclusive) becomes ``(100, 900)``.
    """
    if start_1based < 1:
        raise CoordinateError(f"1-based start must be >= 1, got {start_1based}")
    if end_1based < start_1based:
        raise CoordinateError(f"1-based end ({end_1based}) must be >= start ({start_1based})")
    return start_1based - 1, end_1based


def display_from_internal(start0: int, end0: int) -> tuple[int, int]:
    """Convert internal 0-based half-open coordinates to 1-based inclusive display."""
    if start0 < 0:
        raise CoordinateError(f"start0 must be >= 0, got {start0}")
    if end0 < start0:
        raise CoordinateError(f"end0 ({end0}) must be >= start0 ({start0})")
    if end0 == start0:
        # Zero-length interval: no valid 1-based inclusive representation exists
        # for an empty range; callers should not create zero-length features.
        raise CoordinateError("cannot display a zero-length interval as 1-based inclusive")
    return start0 + 1, end0


def shift_point0(point0: int, delta: int) -> int:
    """Shift a 0-based coordinate by delta, never below zero."""
    result = point0 + delta
    if result < 0:
        raise CoordinateError(f"shifted coordinate {result} would be negative")
    return result


def wrap_point0(point0: int, sequence_length: int) -> int:
    """Wrap a 0-based coordinate modulo a circular sequence length."""
    if sequence_length <= 0:
        raise CoordinateError("sequence_length must be positive to wrap coordinates")
    return point0 % sequence_length
