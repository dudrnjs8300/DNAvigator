"""Manual feature create/update/delete, wired through the undo stack.

Coordinate conversion happens here at the UI/domain boundary: callers pass
1-based inclusive coordinates (as the user sees and types them); everything
stored internally is 0-based half-open.
"""

from __future__ import annotations

from dataclasses import dataclass

from genome_workbench.application.commands import (
    FeatureCreateCommand,
    FeatureDeleteCommand,
    FeatureUpdateCommand,
)
from genome_workbench.application.project_service import ProjectService
from genome_workbench.domain.coordinates import Interval0
from genome_workbench.domain.events import EventType
from genome_workbench.domain.locations import (
    LocationOperator,
    LocationPart,
    build_ordered_parts_from_display_segments,
    extract_sequence,
)
from genome_workbench.domain.models import Feature, Provenance, SequenceRecord, utc_now
from genome_workbench.domain.qualifiers import QualifierSet
from genome_workbench.domain.sequence_ops import TranslationResult, translate
from genome_workbench.domain.validation import ValidationIssue, validate_feature


@dataclass(frozen=True, slots=True)
class FeaturePreview:
    length: int
    nucleotide: str
    translation: TranslationResult | None
    issues: list[ValidationIssue]


class AnnotationService:
    def __init__(self, project_service: ProjectService) -> None:
        self._project_service = project_service

    def preview_simple_feature(
        self,
        record: SequenceRecord,
        start_1based: int,
        end_1based: int,
        strand: int | None,
        feature_type: str,
        genetic_code: int = 11,
    ) -> FeaturePreview:
        interval = Interval0.from_display(start_1based, end_1based)
        part = LocationPart(start0=interval.start0, end0=interval.end0, order_index=0)
        nucleotide = extract_sequence(record.sequence, [part], strand, record.length)
        translation = (
            translate(nucleotide, genetic_code=genetic_code) if feature_type == "CDS" else None
        )
        temp_feature = Feature(record_id=record.id, type=feature_type, strand=strand, parts=[part])
        issues = validate_feature(temp_feature, record, genetic_code)
        return FeaturePreview(
            length=interval.length, nucleotide=nucleotide, translation=translation, issues=issues
        )

    def create_simple_feature(
        self,
        record: SequenceRecord,
        start_1based: int,
        end_1based: int,
        strand: int | None,
        feature_type: str,
        qualifiers: QualifierSet,
        provenance: Provenance | None = None,
    ) -> Feature:
        interval = Interval0.from_display(start_1based, end_1based)
        part = LocationPart(start0=interval.start0, end0=interval.end0, order_index=0)

        provenance_id: str | None = None
        repo = self._project_service.require_writable()
        if provenance is not None:
            repo.save_provenance(provenance)
            provenance_id = provenance.id

        feature = Feature(
            record_id=record.id,
            type=feature_type,
            strand=strand,
            location_operator=LocationOperator.SIMPLE,
            parts=[part],
            qualifiers=qualifiers,
            provenance_id=provenance_id,
        )
        command = FeatureCreateCommand(repo, feature)
        self._project_service.undo_stack.push(command)
        source = "BLAST evidence" if provenance is not None else "Manual"
        self._project_service.log_audit(
            EventType.FEATURE_CREATE,
            feature.id,
            f"Created {feature.type} feature at {start_1based}..{end_1based} ({source})",
        )
        self._project_service.touch()
        return feature

    def preview_compound_feature(
        self,
        record: SequenceRecord,
        segments_1based: list[tuple[int, int]],
        strand: int | None,
        feature_type: str,
        genetic_code: int = 11,
    ) -> FeaturePreview:
        ordered_parts = self._build_ordered_parts(segments_1based, strand)
        nucleotide = extract_sequence(record.sequence, ordered_parts, strand, record.length)
        translation = (
            translate(nucleotide, genetic_code=genetic_code) if feature_type == "CDS" else None
        )
        temp_feature = Feature(
            record_id=record.id, type=feature_type, strand=strand, parts=ordered_parts
        )
        issues = validate_feature(temp_feature, record, genetic_code)
        total_length = sum(p.length for p in ordered_parts)
        return FeaturePreview(
            length=total_length, nucleotide=nucleotide, translation=translation, issues=issues
        )

    def create_compound_feature(
        self,
        record: SequenceRecord,
        segments_1based: list[tuple[int, int]],
        strand: int | None,
        feature_type: str,
        qualifiers: QualifierSet,
        provenance: Provenance | None = None,
    ) -> Feature:
        ordered_parts = self._build_ordered_parts(segments_1based, strand)

        provenance_id: str | None = None
        repo = self._project_service.require_writable()
        if provenance is not None:
            repo.save_provenance(provenance)
            provenance_id = provenance.id

        feature = Feature(
            record_id=record.id,
            type=feature_type,
            strand=strand,
            location_operator=LocationOperator.JOIN,
            parts=ordered_parts,
            qualifiers=qualifiers,
            provenance_id=provenance_id,
        )
        command = FeatureCreateCommand(repo, feature)
        self._project_service.undo_stack.push(command)
        span = ", ".join(f"{s}..{e}" for s, e in segments_1based)
        self._project_service.log_audit(
            EventType.FEATURE_CREATE, feature.id, f"Created {feature.type} join feature at {span}"
        )
        self._project_service.touch()
        return feature

    @staticmethod
    def _build_ordered_parts(
        segments_1based: list[tuple[int, int]], strand: int | None
    ) -> list[LocationPart]:
        return build_ordered_parts_from_display_segments(segments_1based, strand)

    def update_feature(self, before: Feature, after: Feature) -> None:
        after.modified_at = utc_now()
        after.revision = before.revision + 1
        repo = self._project_service.require_writable()
        command = FeatureUpdateCommand(repo, before, after)
        self._project_service.undo_stack.push(command)
        self._project_service.log_audit(
            EventType.FEATURE_UPDATE, after.id, f"Updated {after.type} feature"
        )
        self._project_service.touch()

    def delete_feature(self, feature: Feature) -> None:
        repo = self._project_service.require_writable()
        command = FeatureDeleteCommand(repo, feature)
        self._project_service.undo_stack.push(command)
        self._project_service.log_audit(
            EventType.FEATURE_DELETE, feature.id, f"Deleted {feature.type} feature"
        )
        self._project_service.touch()
