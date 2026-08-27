"""Per-residue color palette for the Alignment View -- same override/persist
pattern as feature_colors.py (D-007: a display preference follows the user
across projects, not one project file), but keyed by single-letter residue
instead of feature type.

Nucleotide and amino acid alphabets both reuse letters (A/C/G/T mean
completely different residues in each), so the two get separate palettes
and separate override namespaces rather than one shared dict.

Cells that match the column's consensus residue are painted at reduced
opacity (blended toward the theme background) and mismatches at full
strength, so differences between sequences pop out visually without a
separate legend or mode switch -- this is what actually answers "where do
these sequences differ" at a glance.
"""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtGui import QColor

from genome_workbench.domain.models import MoleculeType
from genome_workbench.infrastructure.filesystem.paths import app_data_dir

DEFAULT_NUCLEOTIDE_COLORS: dict[str, str] = {
    "A": "#4daf4a",
    "C": "#377eb8",
    "G": "#4d4d4d",
    "T": "#e41a1c",
    "U": "#e41a1c",
    "N": "#9aa0a6",
}

# Grouped by chemical property (hydrophobic / polar / acidic / basic / special).
DEFAULT_AMINO_ACID_COLORS: dict[str, str] = {
    "A": "#f0a848",
    "V": "#f0a848",
    "L": "#f0a848",
    "I": "#f0a848",
    "M": "#f0a848",
    "F": "#f0a848",
    "W": "#f0a848",
    "C": "#f0a848",
    "G": "#e8c840",
    "P": "#e8c840",
    "S": "#3aa66b",
    "T": "#3aa66b",
    "N": "#3aa66b",
    "Q": "#3aa66b",
    "Y": "#3aa66b",
    "D": "#c0392b",
    "E": "#c0392b",
    "H": "#7c6fd1",
    "K": "#7c6fd1",
    "R": "#7c6fd1",
}
DEFAULT_COLOR = "#9aa0a6"
GAP_COLOR = "#d8dade"
_MATCH_OPACITY = 0.35  # cells matching the column consensus are dimmed this much


def _palette_for(molecule_type: MoleculeType) -> dict[str, str]:
    return (
        DEFAULT_AMINO_ACID_COLORS
        if molecule_type == MoleculeType.PROTEIN
        else DEFAULT_NUCLEOTIDE_COLORS
    )


def _namespace_for(molecule_type: MoleculeType) -> str:
    return "amino_acid" if molecule_type == MoleculeType.PROTEIN else "nucleotide"


def residue_color(
    residue: str,
    molecule_type: MoleculeType = MoleculeType.DNA,
    overrides: dict[str, str] | None = None,
) -> QColor:
    residue = residue.upper()
    if residue in ("-", "."):
        return QColor(GAP_COLOR)
    if overrides and residue in overrides:
        return QColor(overrides[residue])
    return QColor(_palette_for(molecule_type).get(residue, DEFAULT_COLOR))


def cell_color(
    residue: str,
    is_consensus_match: bool,
    molecule_type: MoleculeType = MoleculeType.DNA,
    overrides: dict[str, str] | None = None,
) -> QColor:
    """The color to paint one alignment cell: full-strength for a residue
    that differs from its column's consensus, dimmed for one that matches --
    that dimming is what makes mismatches visually pop without extra UI.
    """
    color = residue_color(residue, molecule_type, overrides)
    if is_consensus_match and residue.upper() not in ("-", "."):
        color.setAlphaF(_MATCH_OPACITY)
    return color


def _overrides_path(directory: Path | None = None) -> Path:
    return (directory if directory is not None else app_data_dir()) / "alignment_colors.json"


def load_color_overrides(directory: Path | None = None) -> dict[str, dict[str, str]]:
    """Returns {"nucleotide": {...}, "amino_acid": {...}}, each a flat
    residue -> "#rrggbb" override dict (missing namespaces default to {})."""
    path = _overrides_path(directory)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(data, dict):
        return {}
    result: dict[str, dict[str, str]] = {}
    for namespace in ("nucleotide", "amino_acid"):
        sub = data.get(namespace)
        if isinstance(sub, dict):
            result[namespace] = {
                k: v for k, v in sub.items() if isinstance(k, str) and isinstance(v, str)
            }
    return result


def save_color_overrides(
    overrides_by_namespace: dict[str, dict[str, str]], directory: Path | None = None
) -> None:
    path = _overrides_path(directory)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(overrides_by_namespace, indent=2, sort_keys=True), encoding="utf-8")


def overrides_for(
    overrides_by_namespace: dict[str, dict[str, str]], molecule_type: MoleculeType
) -> dict[str, str]:
    return overrides_by_namespace.get(_namespace_for(molecule_type), {})
