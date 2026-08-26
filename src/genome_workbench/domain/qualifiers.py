"""Ordered, multi-value qualifier storage.

Qualifier values are never collapsed to a single string: GenBank/GFF3 features
routinely carry multiple values for the same key (e.g. multiple ``/db_xref``),
and unknown qualifiers must round-trip unchanged.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field


@dataclass(slots=True)
class QualifierSet:
    """Preserves qualifier key order (first-seen) and per-key value order.

    A "flag" qualifier (present with no value, e.g. ``/pseudo``) is stored as
    an empty string value so its presence is not lost.
    """

    _order: list[str] = field(default_factory=list)
    _values: dict[str, list[str]] = field(default_factory=dict)

    def add(self, key: str, value: str = "") -> None:
        if key not in self._values:
            self._order.append(key)
            self._values[key] = []
        self._values[key].append(value)

    def set_all(self, key: str, values: list[str]) -> None:
        if key not in self._values:
            self._order.append(key)
        self._values[key] = list(values)

    def remove_key(self, key: str) -> None:
        if key in self._values:
            self._order.remove(key)
            del self._values[key]

    def get(self, key: str) -> list[str]:
        return list(self._values.get(key, []))

    def get_first(self, key: str) -> str | None:
        values = self._values.get(key)
        return values[0] if values else None

    def has(self, key: str) -> bool:
        return key in self._values

    def keys(self) -> list[str]:
        return list(self._order)

    def items(self) -> Iterator[tuple[str, list[str]]]:
        for key in self._order:
            yield key, self._values[key]

    def is_empty(self) -> bool:
        return not self._order

    def copy(self) -> QualifierSet:
        clone = QualifierSet()
        for key, values in self.items():
            clone.set_all(key, values)
        return clone

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, QualifierSet):
            return NotImplemented
        return self._order == other._order and self._values == other._values

    def __len__(self) -> int:
        return len(self._order)

    @classmethod
    def from_pairs(cls, pairs: list[tuple[str, str]]) -> QualifierSet:
        qs = cls()
        for key, value in pairs:
            qs.add(key, value)
        return qs
