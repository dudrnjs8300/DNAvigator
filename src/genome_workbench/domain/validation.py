"""Feature/record validation rules producing structured issues (never silent)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from genome_workbench.domain.models import Feature, SequenceRecord
from genome_workbench.domain.sequence_ops import translate


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    severity: Severity
    code: str
    message: str
    feature_id: str | None = None
    record_id: str | None = None


def validate_feature_bounds(feature: Feature, record: SequenceRecord) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for part in feature.parts:
        if part.start0 < 0 or part.end0 > record.length:
            issues.append(
                ValidationIssue(
                    severity=Severity.ERROR,
                    code="coordinate_out_of_range",
                    message=(
                        f"Location part [{part.start0}, {part.end0}) is outside "
                        f"record length {record.length}"
                    ),
                    feature_id=feature.id,
                    record_id=record.id,
                )
            )
        if part.end0 < part.start0:
            issues.append(
                ValidationIssue(
                    severity=Severity.ERROR,
                    code="start_after_end",
                    message=f"start0 {part.start0} is after end0 {part.end0}",
                    feature_id=feature.id,
                    record_id=record.id,
                )
            )
    return issues


def validate_cds_translation(
    feature: Feature,
    biological_nucleotide: str,
    genetic_code: int = 11,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if feature.type != "CDS":
        return issues

    length = len(biological_nucleotide)
    if length % 3 != 0:
        issues.append(
            ValidationIssue(
                severity=Severity.WARNING,
                code="cds_length_not_multiple_of_three",
                message=f"CDS length {length} is not a multiple of 3",
                feature_id=feature.id,
            )
        )

    codon_start_offset = (feature.phase or 0) if feature.phase in (0, 1, 2) else 0
    result = translate(
        biological_nucleotide, genetic_code=genetic_code, codon_start_offset=codon_start_offset
    )

    if not result.has_start_codon:
        issues.append(
            ValidationIssue(
                severity=Severity.WARNING,
                code="missing_start_codon",
                message="Expected start codon not found",
                feature_id=feature.id,
            )
        )
    if not result.has_stop_codon:
        issues.append(
            ValidationIssue(
                severity=Severity.WARNING,
                code="missing_stop_codon",
                message="Expected stop codon not found",
                feature_id=feature.id,
            )
        )
    if result.internal_stop_count > 0:
        issues.append(
            ValidationIssue(
                severity=Severity.WARNING,
                code="internal_stop_codon",
                message=f"{result.internal_stop_count} internal stop codon(s) found",
                feature_id=feature.id,
            )
        )
    return issues


def validate_feature(
    feature: Feature,
    record: SequenceRecord,
    genetic_code: int = 11,
) -> list[ValidationIssue]:
    issues = validate_feature_bounds(feature, record)
    if any(i.severity == Severity.ERROR for i in issues):
        return issues
    if feature.type == "CDS":
        from genome_workbench.domain.locations import extract_sequence

        biological = extract_sequence(record.sequence, feature.parts, feature.strand, record.length)
        issues.extend(validate_cds_translation(feature, biological, genetic_code))
    return issues
