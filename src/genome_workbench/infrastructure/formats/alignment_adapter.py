"""Multiple-sequence-alignment import adapter. Uses Biopython's AlignIO under
an adapter boundary, same pattern as fasta_adapter.py -- the domain layer
never imports Biopython directly.

Format is guessed from the file extension first (fast, no ambiguity for the
common cases); if that fails to parse, every format AlignIO understands for
this use case is tried in turn so a mislabeled extension still loads.
"""

from __future__ import annotations

import gzip
from dataclasses import dataclass, field
from pathlib import Path

from Bio import AlignIO

from genome_workbench.domain.models import Alignment, AlignmentSequence
from genome_workbench.infrastructure.formats.fasta_adapter import guess_molecule_type
from genome_workbench.infrastructure.formats.format_sniffer import is_gzipped
from genome_workbench.infrastructure.formats.issues import ImportIssue, ImportSeverity

_EXTENSION_FORMATS: dict[str, str] = {
    ".aln": "clustal",
    ".clustal": "clustal",
    ".sto": "stockholm",
    ".stockholm": "stockholm",
    ".phy": "phylip-relaxed",
    ".phylip": "phylip-relaxed",
    ".nex": "nexus",
    ".nexus": "nexus",
    ".msf": "msf",
    ".fasta": "fasta",
    ".fa": "fasta",
    ".fna": "fasta",
    ".afa": "fasta",
}
_FALLBACK_FORMATS = ["fasta", "clustal", "stockholm", "phylip-relaxed", "nexus", "msf"]


@dataclass(slots=True)
class AlignmentImportResult:
    alignments: list[Alignment] = field(default_factory=list)
    sequences_by_alignment_id: dict[str, list[AlignmentSequence]] = field(default_factory=dict)
    issues: list[ImportIssue] = field(default_factory=list)


def read_alignment(path: Path) -> AlignmentImportResult:
    path = Path(path)
    result = AlignmentImportResult()

    stripped = path.name.lower()
    if stripped.endswith(".gz"):
        stripped = stripped[: -len(".gz")]
    ext = Path(stripped).suffix
    tried_formats = [_EXTENSION_FORMATS[ext]] if ext in _EXTENSION_FORMATS else []
    tried_formats += [f for f in _FALLBACK_FORMATS if f not in tried_formats]

    opener = gzip.open if is_gzipped(path) else open
    blocks: list = []
    last_error: Exception | None = None
    for fmt in tried_formats:
        try:
            with opener(path, "rt", encoding="utf-8-sig", errors="replace") as handle:
                blocks = list(AlignIO.parse(handle, fmt))
            if blocks:
                break
        except Exception as exc:  # noqa: BLE001 - AlignIO raises many different types
            last_error = exc
            blocks = []
            continue

    if not blocks:
        detail = f": {last_error}" if last_error is not None else ""
        result.issues.append(
            ImportIssue(
                ImportSeverity.ERROR,
                "unrecognized_alignment_format",
                f"Could not parse '{path.name}' as any known alignment format "
                f"(tried {', '.join(tried_formats)}){detail}",
            )
        )
        return result

    base_name = path.stem
    for block_index, block in enumerate(blocks):
        rows = list(block)
        if not rows:
            continue
        length = block.get_alignment_length()
        sequences = str(rows[0].seq).upper()
        molecule_type = guess_molecule_type(sequences)

        alignment = Alignment(
            name=base_name if len(blocks) == 1 else f"{base_name} ({block_index + 1})",
            molecule_type=molecule_type,
            length=length,
            source_format=path.suffix.lstrip(".") or "alignment",
        )
        seq_rows = []
        seen_labels: dict[str, int] = {}
        for order_index, row in enumerate(rows):
            label = row.id or f"seq_{order_index + 1}"
            if label in seen_labels:
                seen_labels[label] += 1
                result.issues.append(
                    ImportIssue(
                        ImportSeverity.WARNING,
                        "duplicate_sequence_label",
                        f"Sequence label '{label}' appears more than once in '{alignment.name}'",
                        label,
                    )
                )
            else:
                seen_labels[label] = 1
            seq_rows.append(
                AlignmentSequence(
                    alignment_id=alignment.id,
                    label=label,
                    sequence=str(row.seq).upper(),
                    order_index=order_index,
                )
            )
        if len(rows) < 2:
            result.issues.append(
                ImportIssue(
                    ImportSeverity.WARNING,
                    "single_sequence_alignment",
                    f"Alignment '{alignment.name}' has only one sequence -- "
                    "there is nothing to compare it against",
                    alignment.name,
                )
            )
        result.alignments.append(alignment)
        result.sequences_by_alignment_id[alignment.id] = seq_rows

    if not result.alignments:
        result.issues.append(
            ImportIssue(
                ImportSeverity.ERROR, "no_alignments_found", "No alignment blocks found in file"
            )
        )
    return result


__all__ = ["AlignmentImportResult", "read_alignment"]
