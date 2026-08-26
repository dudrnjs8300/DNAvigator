"""GFF3 import/export adapter (Sequence Ontology GFF3 specification).

Discontinuous features (multiple lines sharing the same ``ID`` attribute)
have no GenBank-style ``complement(join(...))`` text wrapper — each line
carries its own explicit ``strand`` column. The de facto convention (used by
GMOD/Apollo/IGV and consistent with how most GFF3 is produced) is that lines
are listed in ascending genomic-start order regardless of strand. On import
we therefore sort a feature's lines by start0 and then apply
:func:`genome_workbench.domain.locations.order_parts_for_strand` to compute
the ``order_index`` our extraction semantics require (see docs/DECISIONS.md
D-002) — for minus-strand features this reverses the ascending order, same
as the GenBank adapter's parts already end up after Biopython parses
``complement(join(...))``. On export we do the inverse: re-derive ascending
genomic order from the stored parts before writing lines.
"""

from __future__ import annotations

import gzip
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import quote, unquote

from genome_workbench.domain.locations import (
    LocationOperator,
    LocationPart,
    order_parts_for_strand,
    sorted_parts,
)
from genome_workbench.domain.models import (
    Feature,
    MoleculeType,
    SequenceRecord,
    Topology,
    new_id,
)
from genome_workbench.domain.qualifiers import QualifierSet
from genome_workbench.infrastructure.filesystem.checksums import sha256_of_text
from genome_workbench.infrastructure.formats.fasta_adapter import guess_molecule_type
from genome_workbench.infrastructure.formats.format_sniffer import is_gzipped
from genome_workbench.infrastructure.formats.issues import ImportIssue, ImportSeverity

_RESERVED_GFF3_ATTR_CHARS = ";=&,\t\n\r"


@dataclass(slots=True)
class Gff3ImportResult:
    records: list[SequenceRecord] = field(default_factory=list)
    features_by_record_id: dict[str, list[Feature]] = field(default_factory=dict)
    issues: list[ImportIssue] = field(default_factory=list)
    unmatched_seqids: set[str] = field(default_factory=set)
    directives: list[str] = field(default_factory=list)


def _unescape(value: str) -> str:
    return unquote(value)


def _escape(value: str) -> str:
    return "".join(quote(ch, safe="") if ch in _RESERVED_GFF3_ATTR_CHARS else ch for ch in value)


def _parse_attributes(raw: str) -> dict[str, list[str]]:
    attributes: dict[str, list[str]] = {}
    if raw == "." or not raw:
        return attributes
    for pair in raw.split(";"):
        pair = pair.strip()
        if not pair or "=" not in pair:
            continue
        key, _, value = pair.partition("=")
        key = _unescape(key.strip())
        values = [_unescape(v) for v in value.split(",")]
        attributes.setdefault(key, []).extend(values)
    return attributes


def _format_attributes(qualifiers: QualifierSet, feature_id: str, parent_id: str | None) -> str:
    parts: list[str] = [f"ID={_escape(feature_id)}"]
    if parent_id:
        parts.append(f"Parent={_escape(parent_id)}")
    for key, values in qualifiers.items():
        if key in ("ID", "Parent"):
            continue
        joined = ",".join(_escape(v) for v in values if v)
        if joined:
            parts.append(f"{key}={joined}")
        elif values:
            parts.append(key)
    return ";".join(parts) if parts else "."


def _strand_from_column(column: str) -> int | None:
    return {"+": 1, "-": -1, "?": 0}.get(column)


def _strand_to_column(strand: int | None) -> str:
    strand_map: dict[int | None, str] = {1: "+", -1: "-", 0: "?"}
    return strand_map.get(strand, ".")


def read_gff3(path: Path, record_id_generator=None) -> Gff3ImportResult:
    make_id = record_id_generator or new_id
    path = Path(path)
    result = Gff3ImportResult()

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

    sequence_region_lengths: dict[str, int] = {}
    embedded_fasta_lines: list[str] = []
    in_fasta_section = False
    feature_rows: list[tuple[list[str], int]] = []

    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.rstrip("\n").rstrip("\r")
        if in_fasta_section:
            embedded_fasta_lines.append(line)
            continue
        if line == "##FASTA":
            in_fasta_section = True
            continue
        if not line:
            continue
        if line.startswith("##sequence-region"):
            tokens = line.split()
            if len(tokens) >= 4:
                sequence_region_lengths[tokens[1]] = int(tokens[3])
            result.directives.append(line)
            continue
        if line.startswith("##"):
            result.directives.append(line)
            continue
        if line.startswith("#"):
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
        feature_rows.append((columns, line_number))

    embedded_sequences: dict[str, str] = {}
    if embedded_fasta_lines:
        embedded_sequences = _parse_embedded_fasta("\n".join(embedded_fasta_lines))

    seqids_in_order: list[str] = []
    rows_by_seqid: dict[str, list[tuple[list[str], int]]] = {}
    for columns, line_number in feature_rows:
        seqid = _unescape(columns[0])
        if seqid not in rows_by_seqid:
            rows_by_seqid[seqid] = []
            seqids_in_order.append(seqid)
        rows_by_seqid[seqid].append((columns, line_number))

    all_seqids = set(seqids_in_order) | set(sequence_region_lengths) | set(embedded_sequences)
    for seqid in sorted(
        all_seqids, key=lambda s: seqids_in_order.index(s) if s in seqids_in_order else -1
    ):
        sequence = embedded_sequences.get(seqid, "")
        molecule_type = guess_molecule_type(sequence) if sequence else MoleculeType.UNKNOWN
        record = SequenceRecord(
            id=make_id(),
            display_id=seqid,
            name=seqid,
            molecule_type=molecule_type,
            topology=Topology.UNKNOWN,
            sequence=sequence,
            checksum_sha256=sha256_of_text(sequence) if sequence else "",
            source_format="gff3",
            source_record_index=len(result.records),
        )
        if not sequence:
            result.unmatched_seqids.add(seqid)
        result.records.append(record)

        features = _build_features_for_seqid(
            rows_by_seqid.get(seqid, []), record.id, make_id, result.issues
        )
        _link_parent_child(features)
        _check_parent_cycles(features, result.issues)
        result.features_by_record_id[record.id] = features

    return result


def _parse_embedded_fasta(text: str) -> dict[str, str]:
    sequences: dict[str, str] = {}
    current_id: str | None = None
    chunks: list[str] = []
    for line in text.splitlines():
        if line.startswith(">"):
            if current_id is not None:
                sequences[current_id] = "".join(chunks).upper()
            current_id = line[1:].split()[0] if line[1:].split() else ""
            chunks = []
        elif current_id is not None:
            chunks.append(line.strip())
    if current_id is not None:
        sequences[current_id] = "".join(chunks).upper()
    return sequences


def _build_features_for_seqid(
    rows: list[tuple[list[str], int]], record_id: str, make_id, issues: list[ImportIssue]
) -> list[Feature]:
    groups: dict[str, list[tuple[list[str], int]]] = {}
    ungrouped: list[tuple[list[str], int]] = []
    group_order: list[str] = []
    for columns, line_number in rows:
        attributes = _parse_attributes(columns[8])
        gff_id = attributes.get("ID", [None])[0]
        if gff_id:
            if gff_id not in groups:
                groups[gff_id] = []
                group_order.append(gff_id)
            groups[gff_id].append((columns, line_number))
        else:
            ungrouped.append((columns, line_number))

    features: list[Feature] = []
    gff_id_to_feature_id: dict[str, str] = {}
    pending_parents: dict[str, list[str]] = {}

    for gff_id in group_order:
        group_rows = groups[gff_id]
        first_columns, _ = group_rows[0]
        attributes = _parse_attributes(first_columns[8])
        parts_ascending: list[LocationPart] = []
        for columns, line_number in group_rows:
            try:
                start0, end0, phase = _parse_location_columns(columns)
            except ValueError as exc:
                issues.append(
                    ImportIssue(
                        ImportSeverity.WARNING, "invalid_coordinates", f"line {line_number}: {exc}"
                    )
                )
                continue
            parts_ascending.append(
                LocationPart(start0=start0, end0=end0, order_index=0, phase=phase)
            )
        if not parts_ascending:
            continue
        parts_ascending.sort(key=lambda p: p.start0)

        strand = _strand_from_column(first_columns[6])
        ordered_parts = order_parts_for_strand(parts_ascending, strand)
        operator = LocationOperator.JOIN if len(ordered_parts) > 1 else LocationOperator.SIMPLE

        feature_id = make_id()
        gff_id_to_feature_id[gff_id] = feature_id
        qualifiers = _attributes_to_qualifiers(attributes)
        parent_refs = attributes.get("Parent", [])
        if parent_refs:
            pending_parents[feature_id] = parent_refs

        score_raw = first_columns[5]
        score = float(score_raw) if score_raw != "." else None

        features.append(
            Feature(
                id=feature_id,
                record_id=record_id,
                type=_unescape(first_columns[2]),
                strand=strand,
                location_operator=operator,
                parts=ordered_parts,
                qualifiers=qualifiers,
                source=_unescape(first_columns[1]) if first_columns[1] != "." else None,
                score=score,
                phase=ordered_parts[0].phase,
            )
        )

    for columns, line_number in ungrouped:
        try:
            start0, end0, phase = _parse_location_columns(columns)
        except ValueError as exc:
            issues.append(
                ImportIssue(
                    ImportSeverity.WARNING, "invalid_coordinates", f"line {line_number}: {exc}"
                )
            )
            continue
        attributes = _parse_attributes(columns[8])
        strand = _strand_from_column(columns[6])
        score_raw = columns[5]
        score = float(score_raw) if score_raw != "." else None
        features.append(
            Feature(
                id=make_id(),
                record_id=record_id,
                type=_unescape(columns[2]),
                strand=strand,
                location_operator=LocationOperator.SIMPLE,
                parts=[LocationPart(start0=start0, end0=end0, order_index=0, phase=phase)],
                qualifiers=_attributes_to_qualifiers(attributes),
                source=_unescape(columns[1]) if columns[1] != "." else None,
                score=score,
                phase=phase,
            )
        )

    for feature in features:
        parent_gff_ids = pending_parents.get(feature.id, [])
        feature.parent_ids = [
            gff_id_to_feature_id[p] for p in parent_gff_ids if p in gff_id_to_feature_id
        ]

    return features


def _parse_location_columns(columns: list[str]) -> tuple[int, int, int | None]:
    start_1based = int(columns[3])
    end_1based = int(columns[4])
    if start_1based < 1 or end_1based < start_1based:
        raise ValueError(f"invalid start/end {columns[3]}/{columns[4]}")
    phase_raw = columns[7]
    phase = int(phase_raw) if phase_raw in ("0", "1", "2") else None
    return start_1based - 1, end_1based, phase


def _attributes_to_qualifiers(attributes: dict[str, list[str]]) -> QualifierSet:
    qualifiers = QualifierSet()
    for key, values in attributes.items():
        if key in ("ID", "Parent"):
            continue
        for value in values:
            qualifiers.add(key, value)
    return qualifiers


def _link_parent_child(features: list[Feature]) -> None:
    by_id = {f.id: f for f in features}
    for feature in features:
        for parent_id in feature.parent_ids:
            parent = by_id.get(parent_id)
            if parent is not None and feature.id not in parent.child_ids:
                parent.child_ids.append(feature.id)


def _check_parent_cycles(features: list[Feature], issues: list[ImportIssue]) -> None:
    by_id = {f.id: f for f in features}
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(feature_id: str) -> bool:
        if feature_id in visiting:
            return True
        if feature_id in visited:
            return False
        visiting.add(feature_id)
        feature = by_id.get(feature_id)
        if feature is not None:
            for parent_id in feature.parent_ids:
                if visit(parent_id):
                    return True
        visiting.discard(feature_id)
        visited.add(feature_id)
        return False

    for feature in features:
        if visit(feature.id):
            issues.append(
                ImportIssue(
                    ImportSeverity.ERROR,
                    "parent_cycle",
                    f"Parent graph cycle detected involving feature {feature.id}",
                )
            )
            break


def write_gff3(
    records: list[SequenceRecord],
    features_by_record_id: dict[str, list[Feature]],
    destination: Path,
    embed_fasta: bool = True,
) -> None:
    lines: list[str] = ["##gff-version 3"]
    for record in records:
        if record.length:
            lines.append(f"##sequence-region {record.display_id} 1 {record.length}")

    for record in records:
        features = features_by_record_id.get(record.id, [])
        for feature in features:
            lines.extend(_feature_to_gff3_lines(feature, record))

    if embed_fasta:
        lines.append("##FASTA")
        for record in records:
            if not record.sequence:
                continue
            lines.append(f">{record.display_id}")
            for i in range(0, len(record.sequence), 70):
                lines.append(record.sequence[i : i + 70])

    Path(destination).write_text("\n".join(lines) + "\n", encoding="utf-8")


def _feature_to_gff3_lines(feature: Feature, record: SequenceRecord) -> list[str]:
    ascending = sorted_parts(feature.parts)
    if feature.strand == -1:
        ascending = list(reversed(ascending))
    ascending = sorted(ascending, key=lambda p: p.start0)

    feature_id = feature.id
    lines: list[str] = []
    for part in ascending:
        start_1based, end_1based = part.start0 + 1, part.end0
        score_col = f"{feature.score:g}" if feature.score is not None else "."
        phase_col = str(part.phase) if part.phase is not None and feature.type == "CDS" else "."
        parent_id = feature.parent_ids[0] if feature.parent_ids else None
        attributes = _format_attributes(feature.qualifiers, feature_id, parent_id)
        lines.append(
            "\t".join(
                [
                    record.display_id,
                    feature.source or ".",
                    feature.type,
                    str(start_1based),
                    str(end_1based),
                    score_col,
                    _strand_to_column(feature.strand),
                    phase_col,
                    attributes,
                ]
            )
        )
    return lines
