"""Sorted-start + bisect interval index for viewport feature queries.

No external dependency: bacterial-scale records (up to ~20,000 features per
spec) are comfortably handled by a linear filter bounded by the largest
feature span, as suggested by spec section 8.3.
"""

from __future__ import annotations

import bisect

from genome_workbench.domain.models import Feature


class FeatureIntervalIndex:
    def __init__(self, features: list[Feature] | None = None) -> None:
        self._sorted: list[Feature] = []
        self._starts: list[int] = []
        self._max_length = 0
        self._by_id: dict[str, Feature] = {}
        if features:
            self.rebuild(features)

    def rebuild(self, features: list[Feature]) -> None:
        self._sorted = sorted(features, key=lambda f: f.start0)
        self._starts = [f.start0 for f in self._sorted]
        self._max_length = max((f.end0 - f.start0 for f in features), default=0)
        self._by_id = {f.id: f for f in features}

    def by_id(self, feature_id: str) -> Feature | None:
        return self._by_id.get(feature_id)

    def query_overlapping(self, start0: int, end0: int) -> list[Feature]:
        if not self._sorted:
            return []
        lo = bisect.bisect_left(self._starts, start0 - self._max_length)
        hi = bisect.bisect_left(self._starts, end0)
        candidates = self._sorted[max(lo, 0) : hi]
        return [f for f in candidates if f.end0 > start0 and f.start0 < end0]

    def __len__(self) -> int:
        return len(self._sorted)
