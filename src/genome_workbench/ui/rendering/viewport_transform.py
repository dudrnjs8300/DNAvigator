"""Genome-coordinate <-> pixel mapping for the genome canvas.

Pure Python/math, no Qt dependency, so zoom/pan arithmetic is unit-testable
without a QApplication.
"""

from __future__ import annotations

from dataclasses import dataclass


class LodLevel:
    OVERVIEW = "overview"  # whole genome / many Mb per screen: density only
    GENE = "gene"  # tens-hundreds of kb: colored arrows, major labels
    FEATURE = "feature"  # kb-scale: all features + labels
    BASE = "base"  # tens-hundreds of bp: literal nucleotide letters


@dataclass(slots=True)
class ViewportTransform:
    view_start0: int
    view_end0: int
    pixel_width: int
    sequence_length: int

    def __post_init__(self) -> None:
        self.view_start0 = max(0, self.view_start0)
        self.view_end0 = min(self.sequence_length, self.view_end0)
        if self.view_end0 <= self.view_start0:
            self.view_end0 = min(self.sequence_length, self.view_start0 + 1)

    @property
    def visible_length(self) -> int:
        return self.view_end0 - self.view_start0

    @property
    def bp_per_pixel(self) -> float:
        return self.visible_length / max(self.pixel_width, 1)

    @property
    def pixels_per_bp(self) -> float:
        bpp = self.bp_per_pixel
        return 1.0 / bpp if bpp > 0 else float(self.pixel_width)

    def genome_to_pixel(self, position0: float) -> float:
        return (position0 - self.view_start0) * self.pixels_per_bp

    def pixel_to_genome(self, x: float) -> int:
        position = self.view_start0 + x * self.bp_per_pixel
        return max(0, min(self.sequence_length, round(position)))

    def lod_level(self) -> str:
        bpp = self.bp_per_pixel
        if bpp >= 100:
            return LodLevel.OVERVIEW
        if bpp >= 5:
            return LodLevel.GENE
        if bpp > 0.6:
            return LodLevel.FEATURE
        return LodLevel.BASE

    def zoomed(self, factor: float, anchor_pixel: float) -> ViewportTransform:
        """Zoom in (factor<1) or out (factor>1) keeping the base under anchor_pixel fixed."""
        anchor_genome = self.view_start0 + anchor_pixel * self.bp_per_pixel
        new_length = max(1, min(self.sequence_length, round(self.visible_length * factor)))
        ratio = anchor_pixel / max(self.pixel_width, 1)
        new_start = round(anchor_genome - ratio * new_length)
        new_end = new_start + new_length
        if new_start < 0:
            new_end -= new_start
            new_start = 0
        if new_end > self.sequence_length:
            new_start -= new_end - self.sequence_length
            new_end = self.sequence_length
            new_start = max(0, new_start)
        return ViewportTransform(new_start, new_end, self.pixel_width, self.sequence_length)

    def panned(self, delta_bp: int) -> ViewportTransform:
        new_start = self.view_start0 + delta_bp
        new_end = self.view_end0 + delta_bp
        if new_start < 0:
            new_end -= new_start
            new_start = 0
        if new_end > self.sequence_length:
            shift = new_end - self.sequence_length
            new_start -= shift
            new_end -= shift
            new_start = max(0, new_start)
        return ViewportTransform(new_start, new_end, self.pixel_width, self.sequence_length)

    def fit_to_range(
        self, start0: int, end0: int, padding_fraction: float = 0.1
    ) -> ViewportTransform:
        span = max(1, end0 - start0)
        padding = max(1, round(span * padding_fraction))
        return ViewportTransform(
            start0 - padding, end0 + padding, self.pixel_width, self.sequence_length
        )

    @classmethod
    def whole_genome(cls, sequence_length: int, pixel_width: int) -> ViewportTransform:
        return cls(0, sequence_length, pixel_width, sequence_length)
