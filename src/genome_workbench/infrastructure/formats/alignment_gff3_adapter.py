"""Attaches GFF3 annotations to the rows of an existing alignment, instead of
creating new records the way gff3_adapter.read_gff3 does. Reuses that
module's line/attribute parsing (shared, not duplicated) but produces
AlignmentFeature rows keyed to whichever AlignmentSequence's label matches
the GFF3 seqid column, in that row's own ungapped coordinate space (the same
space a GFF3 made from that isolate's raw assembly already uses).

Deliberately ignores ID/Parent grouping: bacterial-genome annotators
(Prokka/Bakta) emit one contiguous line per gene, and every line becomes its
own single-span AlignmentFeature regardless of grouping -- see
domain/models.py::AlignmentFeature for why compound/join spans are out of
scope here.
"""

from __future__ import annotations

import gzip
from dataclasses import dataclass, field
from pathlib import Path

from genome_workbench.domain.models import AlignmentFeature, AlignmentSequence, new_id
from genome_workbench.infrastructure.formats.format_sniffer import is_gzipped
from genome_workbench.infrastructure.formats.gff3_adapter import (
    _attributes_to_qualifiers,
    _parse_attributes,
    _parse_location_columns,
    _strand_from_column,
    _unescape,
)
from genome_workbench.infrastructure.formats.issues import ImportIssue, ImportSeverity


@dataclass(slots=True)
class AlignmentGff3ImportResult:
    features: list[AlignmentFeature] = field(default_factory=list)
    issues: list[ImportIssue] = field(default_factory=list)
    unmatched_seqids: set[str] = field(default_factory=set)


def read_alignment_gff3(
    path: Path, sequences: list[AlignmentSequence]
) -> AlignmentGff3ImportResult:
    path = Path(path)
    result = AlignmentGff3ImportResult()
    sequence_id_by_label = {seq.label: seq.id for seq in sequences}

    opener = gzip.open if is_gzipped(path) else open
    with opener(path, "rt", encoding="utf-8-sig", errors="replace") as handle:
        lines = handle.readlines()

    if not lines or not lines[0].strip().startswith("##gff-version 3"):
        result.issues.append(
            ImportIssue(
                ImportSeverity.ERROR,
                "not_gff3",
                "File does not start with '##gff-version 3'; refusing to guess-parse it as GFF3",
            )
        )
        return result

    seen_seqids: set[str] = set()
    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.rstrip("\n").rstrip("\r")
        if not line or line.startswith("#"):
            continue
        columns = line.split("\t")
        if len(columns) != 9:
            result.issues.append(
                ImportIssue(
                    ImportSeverity.WARNING,
                    "malformed_line",
                    f"line {line_number}: expected 9 columns, got {len(columns)}",
                )
            )
            continue

        seqid = _unescape(columns[0])
        alignment_sequence_id = sequence_id_by_label.get(seqid)
        if alignment_sequence_id is None:
            if seqid not in seen_seqids:
                seen_seqids.add(seqid)
                result.unmatched_seqids.add(seqid)
                result.issues.append(
                    ImportIssue(
                        ImportSeverity.WARNING,
                        "unmatched_seqid",
                        f"GFF3 seqid '{seqid}' does not match any sequence label in this "
                        "alignment -- its annotations were skipped",
                    )
                )
            continue

        try:
            start0, end0, _phase = _parse_location_columns(columns)
        except ValueError as exc:
            result.issues.append(
                ImportIssue(
                    ImportSeverity.WARNING, "invalid_coordinates", f"line {line_number}: {exc}"
                )
            )
            continue

        attributes = _parse_attributes(columns[8])
        result.features.append(
            AlignmentFeature(
                id=new_id(),
                alignment_sequence_id=alignment_sequence_id,
                type=_unescape(columns[2]),
                strand=_strand_from_column(columns[6]),
                start0=start0,
                end0=end0,
                qualifiers=_attributes_to_qualifiers(attributes),
            )
        )

    if not result.features and not result.issues:
        result.issues.append(
            ImportIssue(ImportSeverity.ERROR, "no_features_found", "No GFF3 features found in file")
        )
    return result
