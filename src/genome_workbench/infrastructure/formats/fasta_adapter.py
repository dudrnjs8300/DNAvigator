"""FASTA import adapter. Uses Biopython's mature FASTA parser under an adapter
boundary — the domain layer never imports Biopython directly.
"""

from __future__ import annotations

import gzip
from dataclasses import dataclass, field
from pathlib import Path

from Bio import SeqIO

from genome_workbench.domain.models import MoleculeType, SequenceRecord, Topology
from genome_workbench.infrastructure.filesystem.checksums import sha256_of_text
from genome_workbench.infrastructure.formats.format_sniffer import is_gzipped
from genome_workbench.infrastructure.formats.issues import ImportIssue, ImportSeverity

_NUCLEOTIDE_ALPHABET = set("ACGTURYSWKMBDHVN")
_ALLOWED_GAP_CHARS = set("-.")


@dataclass(slots=True)
class FastaImportResult:
    records: list[SequenceRecord] = field(default_factory=list)
    issues: list[ImportIssue] = field(default_factory=list)
    raw_headers: dict[str, str] = field(default_factory=dict)  # record.id -> original header


def guess_molecule_type(sequence: str) -> MoleculeType:
    upper = sequence.upper()
    if not upper:
        return MoleculeType.UNKNOWN
    residues = set(upper) - _ALLOWED_GAP_CHARS
    non_nucleotide = residues - _NUCLEOTIDE_ALPHABET
    if not non_nucleotide:
        return MoleculeType.RNA if "U" in residues and "T" not in residues else MoleculeType.DNA
    return MoleculeType.PROTEIN


def read_fasta(
    path: Path,
    molecule_type_hint: MoleculeType | None = None,
    source_format_label: str = "fasta",
) -> FastaImportResult:
    path = Path(path)
    result = FastaImportResult()
    seen_display_ids: dict[str, int] = {}

    opener = gzip.open if is_gzipped(path) else open
    mode = "rt"
    with opener(path, mode, encoding="utf-8-sig", errors="replace") as handle:
        index = 0
        for bio_record in SeqIO.parse(handle, "fasta"):
            display_id = bio_record.id
            sequence = str(bio_record.seq).upper()

            if display_id in seen_display_ids:
                seen_display_ids[display_id] += 1
                result.issues.append(
                    ImportIssue(
                        ImportSeverity.WARNING,
                        "duplicate_record_id",
                        f"Record ID '{display_id}' appears more than once in the file",
                        display_id,
                    )
                )
            else:
                seen_display_ids[display_id] = 1

            if len(sequence) == 0:
                result.issues.append(
                    ImportIssue(
                        ImportSeverity.ERROR,
                        "zero_length_record",
                        f"Record '{display_id}' has zero length and was skipped",
                        display_id,
                    )
                )
                index += 1
                continue

            molecule_type = molecule_type_hint or guess_molecule_type(sequence)
            invalid_chars = _find_invalid_symbols(sequence, molecule_type)
            if invalid_chars:
                result.issues.append(
                    ImportIssue(
                        ImportSeverity.WARNING,
                        "invalid_symbols",
                        f"Record '{display_id}' contains unexpected symbols: "
                        f"{sorted(invalid_chars)}",
                        display_id,
                    )
                )

            record = SequenceRecord(
                display_id=display_id,
                name=bio_record.name or display_id,
                description=bio_record.description,
                molecule_type=molecule_type,
                topology=Topology.UNKNOWN,
                sequence=sequence,
                checksum_sha256=sha256_of_text(sequence),
                source_format=source_format_label,
                source_record_index=index,
            )
            result.records.append(record)
            result.raw_headers[record.id] = bio_record.description
            index += 1

    if not result.records and not result.issues:
        result.issues.append(
            ImportIssue(ImportSeverity.ERROR, "no_records_found", "No FASTA records found in file")
        )
    return result


def _find_invalid_symbols(sequence: str, molecule_type: MoleculeType) -> set[str]:
    residues = set(sequence) - _ALLOWED_GAP_CHARS
    if molecule_type == MoleculeType.PROTEIN:
        allowed = set("ACDEFGHIKLMNPQRSTVWYXBZJUO*")
    else:
        allowed = _NUCLEOTIDE_ALPHABET
    return residues - allowed
