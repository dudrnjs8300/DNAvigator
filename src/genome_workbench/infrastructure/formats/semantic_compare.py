"""Semantic (not byte-identical) round-trip comparison.

Export writers reformat text (whitespace, wrapping, library version
differences). What must be preserved is the *biological meaning*: sequence,
molecule type, topology, feature count/type/location/strand, qualifiers, and
extracted/translated CDS sequences. IDs are expected to differ across
export-reimport (new UUIDs are minted on import), so records and features are
matched by position/content, never by ID.
"""

from __future__ import annotations

from dataclasses import dataclass

from genome_workbench.domain.locations import extract_sequence, sorted_parts
from genome_workbench.domain.models import Feature, SequenceRecord
from genome_workbench.domain.sequence_ops import translate
from genome_workbench.infrastructure.filesystem.checksums import sha256_of_text


class DiffSeverity:
    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True, slots=True)
class SemanticDiff:
    severity: str
    code: str
    message: str


def _feature_sort_key(feature: Feature) -> tuple:
    parts = sorted_parts(feature.parts)
    return (parts[0].start0 if parts else -1, parts[-1].end0 if parts else -1, feature.type)


def compare_semantic(
    records_a: list[SequenceRecord],
    features_a: dict[str, list[Feature]],
    records_b: list[SequenceRecord],
    features_b: dict[str, list[Feature]],
    genetic_code: int = 11,
) -> list[SemanticDiff]:
    diffs: list[SemanticDiff] = []

    if len(records_a) != len(records_b):
        diffs.append(
            SemanticDiff(
                DiffSeverity.ERROR,
                "record_count_mismatch",
                f"record count differs: {len(records_a)} vs {len(records_b)}",
            )
        )
        return diffs

    for i, (rec_a, rec_b) in enumerate(zip(records_a, records_b, strict=True)):
        diffs.extend(_compare_record_pair(i, rec_a, rec_b))
        diffs.extend(
            _compare_feature_lists(
                i,
                features_a.get(rec_a.id, []),
                features_b.get(rec_b.id, []),
                rec_a.sequence,
                rec_b.sequence,
                genetic_code,
            )
        )
    return diffs


def _compare_record_pair(index: int, a: SequenceRecord, b: SequenceRecord) -> list[SemanticDiff]:
    diffs: list[SemanticDiff] = []
    checksum_a = sha256_of_text(a.sequence)
    checksum_b = sha256_of_text(b.sequence)
    if checksum_a != checksum_b:
        diffs.append(
            SemanticDiff(
                DiffSeverity.ERROR,
                "sequence_checksum_mismatch",
                f"record[{index}] sequence checksum differs",
            )
        )
    if a.molecule_type != b.molecule_type:
        diffs.append(
            SemanticDiff(
                DiffSeverity.ERROR,
                "molecule_type_mismatch",
                f"record[{index}] molecule_type {a.molecule_type} vs {b.molecule_type}",
            )
        )
    if a.topology != b.topology:
        diffs.append(
            SemanticDiff(
                DiffSeverity.WARNING,
                "topology_mismatch",
                f"record[{index}] topology {a.topology} vs {b.topology}",
            )
        )
    return diffs


def _compare_feature_lists(
    record_index: int,
    features_a: list[Feature],
    features_b: list[Feature],
    sequence_a: str,
    sequence_b: str,
    genetic_code: int,
) -> list[SemanticDiff]:
    diffs: list[SemanticDiff] = []
    if len(features_a) != len(features_b):
        diffs.append(
            SemanticDiff(
                DiffSeverity.ERROR,
                "feature_count_mismatch",
                f"record[{record_index}] feature count differs: "
                f"{len(features_a)} vs {len(features_b)}",
            )
        )
        return diffs

    sorted_a = sorted(features_a, key=_feature_sort_key)
    sorted_b = sorted(features_b, key=_feature_sort_key)

    for feature_index, (fa, fb) in enumerate(zip(sorted_a, sorted_b, strict=True)):
        label = f"record[{record_index}].feature[{feature_index}]"
        if fa.type != fb.type:
            diffs.append(
                SemanticDiff(
                    DiffSeverity.ERROR,
                    "feature_type_mismatch",
                    f"{label} type {fa.type} vs {fb.type}",
                )
            )
        if fa.strand != fb.strand:
            diffs.append(
                SemanticDiff(
                    DiffSeverity.ERROR,
                    "feature_strand_mismatch",
                    f"{label} strand {fa.strand} vs {fb.strand}",
                )
            )
        parts_a = [(p.start0, p.end0) for p in sorted_parts(fa.parts)]
        parts_b = [(p.start0, p.end0) for p in sorted_parts(fb.parts)]
        if parts_a != parts_b:
            diffs.append(
                SemanticDiff(
                    DiffSeverity.ERROR,
                    "feature_location_mismatch",
                    f"{label} location parts {parts_a} vs {parts_b}",
                )
            )
        if fa.qualifiers.keys() != fb.qualifiers.keys():
            diffs.append(
                SemanticDiff(
                    DiffSeverity.WARNING,
                    "qualifier_keys_mismatch",
                    f"{label} qualifier keys {fa.qualifiers.keys()} vs {fb.qualifiers.keys()}",
                )
            )
        else:
            for key, values_a in fa.qualifiers.items():
                if values_a != fb.qualifiers.get(key):
                    diffs.append(
                        SemanticDiff(
                            DiffSeverity.ERROR,
                            "qualifier_value_mismatch",
                            f"{label} qualifier '{key}' values differ",
                        )
                    )

        if fa.type == "CDS" and parts_a == parts_b and fa.strand == fb.strand:
            try:
                nt_a = extract_sequence(sequence_a, fa.parts, fa.strand, len(sequence_a))
                nt_b = extract_sequence(sequence_b, fb.parts, fb.strand, len(sequence_b))
            except Exception as exc:  # noqa: BLE001
                diffs.append(
                    SemanticDiff(DiffSeverity.ERROR, "cds_extraction_failed", f"{label}: {exc}")
                )
            else:
                if sha256_of_text(nt_a) != sha256_of_text(nt_b):
                    diffs.append(
                        SemanticDiff(DiffSeverity.ERROR, "cds_nucleotide_checksum_mismatch", label)
                    )
                offset = (fa.phase or 0) if fa.phase in (0, 1, 2) else 0
                protein_a = translate(
                    nt_a, genetic_code=genetic_code, codon_start_offset=offset
                ).protein
                protein_b = translate(
                    nt_b, genetic_code=genetic_code, codon_start_offset=offset
                ).protein
                if sha256_of_text(protein_a) != sha256_of_text(protein_b):
                    diffs.append(
                        SemanticDiff(DiffSeverity.ERROR, "cds_translation_checksum_mismatch", label)
                    )
    return diffs
