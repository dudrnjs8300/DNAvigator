"""Additional P0 export formats (spec 6.6): nucleotide/protein FASTA, FFN
(CDS nucleotide), and a feature table CSV/TSV. These are one-way exports
(no matching import adapter/round-trip validation) — GenBank/GFF3 remain the
canonical re-importable formats.
"""

from __future__ import annotations

import csv
from pathlib import Path

from genome_workbench.domain.coordinates import display_from_internal
from genome_workbench.domain.locations import extract_sequence
from genome_workbench.domain.models import Feature, MoleculeType, SequenceRecord
from genome_workbench.domain.sequence_ops import translate


def _write_fasta_records(pairs: list[tuple[str, str]], destination: Path) -> None:
    lines = []
    for header, sequence in pairs:
        lines.append(f">{header}")
        for i in range(0, len(sequence), 70):
            lines.append(sequence[i : i + 70])
    Path(destination).write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def write_nucleotide_fasta(records: list[SequenceRecord], destination: Path) -> int:
    """Write every non-protein record. Returns the number of records written."""
    pairs = [
        (f"{r.display_id} {r.description}".strip(), r.sequence)
        for r in records
        if r.molecule_type != MoleculeType.PROTEIN
    ]
    _write_fasta_records(pairs, destination)
    return len(pairs)


def write_protein_fasta_from_records(records: list[SequenceRecord], destination: Path) -> int:
    """Write protein-molecule-type records directly (not translated CDS)."""
    pairs = [
        (f"{r.display_id} {r.description}".strip(), r.sequence)
        for r in records
        if r.molecule_type == MoleculeType.PROTEIN
    ]
    _write_fasta_records(pairs, destination)
    return len(pairs)


def _cds_header(record: SequenceRecord, feature: Feature) -> str:
    label = (
        feature.qualifiers.get_first("locus_tag")
        or feature.qualifiers.get_first("gene")
        or feature.id
    )
    product = feature.qualifiers.get_first("product") or ""
    start_disp, end_disp = display_from_internal(feature.start0, feature.end0)
    strand_map: dict[int | None, str] = {1: "+", -1: "-"}
    strand_text = strand_map.get(feature.strand, "?")
    header = f"{label} [{record.display_id}:{start_disp}-{end_disp}({strand_text})]"
    if product:
        header += f" {product}"
    return header


def write_protein_fasta_from_cds(
    records: list[SequenceRecord],
    features_by_record_id: dict[str, list[Feature]],
    destination: Path,
    genetic_code: int = 11,
) -> int:
    """Translate every CDS feature and write as protein FASTA."""
    pairs = []
    for record in records:
        for feature in features_by_record_id.get(record.id, []):
            if feature.type != "CDS":
                continue
            offset = (feature.phase or 0) if feature.phase in (0, 1, 2) else 0
            nucleotide = extract_sequence(
                record.sequence, feature.parts, feature.strand, record.length
            )
            protein = translate(
                nucleotide, genetic_code=genetic_code, codon_start_offset=offset
            ).protein
            pairs.append((_cds_header(record, feature), protein))
    _write_fasta_records(pairs, destination)
    return len(pairs)


def write_ffn(
    records: list[SequenceRecord],
    features_by_record_id: dict[str, list[Feature]],
    destination: Path,
) -> int:
    """Write the biological (strand-corrected) nucleotide sequence of every CDS feature."""
    pairs = []
    for record in records:
        for feature in features_by_record_id.get(record.id, []):
            if feature.type != "CDS":
                continue
            nucleotide = extract_sequence(
                record.sequence, feature.parts, feature.strand, record.length
            )
            pairs.append((_cds_header(record, feature), nucleotide))
    _write_fasta_records(pairs, destination)
    return len(pairs)


_CSV_COLUMNS = [
    "record_id",
    "feature_id",
    "type",
    "start_1based",
    "end_1based",
    "strand",
    "length",
    "gene",
    "locus_tag",
    "product",
    "note",
    "source",
    "provenance_id",
]


def write_feature_table_csv(
    records: list[SequenceRecord],
    features_by_record_id: dict[str, list[Feature]],
    destination: Path,
    delimiter: str = ",",
) -> int:
    row_count = 0
    with open(destination, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, delimiter=delimiter)
        writer.writerow(_CSV_COLUMNS)
        for record in records:
            for feature in features_by_record_id.get(record.id, []):
                start_disp, end_disp = display_from_internal(feature.start0, feature.end0)
                strand_map: dict[int | None, str] = {1: "+", -1: "-"}
                strand_text = strand_map.get(feature.strand, "")
                writer.writerow(
                    [
                        record.display_id,
                        feature.id,
                        feature.type,
                        start_disp,
                        end_disp,
                        strand_text,
                        feature.length,
                        feature.qualifiers.get_first("gene") or "",
                        feature.qualifiers.get_first("locus_tag") or "",
                        feature.qualifiers.get_first("product") or "",
                        feature.qualifiers.get_first("note") or "",
                        feature.source or "",
                        feature.provenance_id or "",
                    ]
                )
                row_count += 1
    return row_count
