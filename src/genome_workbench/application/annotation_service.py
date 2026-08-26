"""Manual feature create/update/delete, wired through the undo stack.

Coordinate conversion happens here at the UI/domain boundary: callers pass
1-based inclusive coordinates (as the user sees and types them); everything
stored internally is 0-based half-open.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace

from genome_workbench.application.commands import (
    BatchCommand,
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
from genome_workbench.infrastructure.filesystem.annotation_templates import AnnotationTemplate


def _copy_feature_with(feature: Feature, **overrides: object) -> Feature:
    return replace(feature, **overrides)  # type: ignore[arg-type]


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
        fuzzy_start: bool = False,
        fuzzy_end: bool = False,
    ) -> FeaturePreview:
        interval = Interval0.from_display(start_1based, end_1based)
        part = LocationPart(
            start0=interval.start0,
            end0=interval.end0,
            order_index=0,
            fuzzy_start=fuzzy_start,
            fuzzy_end=fuzzy_end,
        )
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
        fuzzy_start: bool = False,
        fuzzy_end: bool = False,
    ) -> Feature:
        interval = Interval0.from_display(start_1based, end_1based)
        part = LocationPart(
            start0=interval.start0,
            end0=interval.end0,
            order_index=0,
            fuzzy_start=fuzzy_start,
            fuzzy_end=fuzzy_end,
        )

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
        segments_1based: Sequence[tuple[int, int] | tuple[int, int, bool, bool]],
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
        segments_1based: Sequence[tuple[int, int] | tuple[int, int, bool, bool]],
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
        span = ", ".join(f"{seg[0]}..{seg[1]}" for seg in segments_1based)
        self._project_service.log_audit(
            EventType.FEATURE_CREATE, feature.id, f"Created {feature.type} join feature at {span}"
        )
        self._project_service.touch()
        return feature

    @staticmethod
    def _build_ordered_parts(
        segments_1based: Sequence[tuple[int, int] | tuple[int, int, bool, bool]],
        strand: int | None,
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

    def batch_update_qualifier(
        self,
        features: list[Feature],
        operation: str,
        key: str,
        value: str = "",
    ) -> list[Feature]:
        """Applies one qualifier operation to many features as a single undo
        step. ``operation`` is "set" (replace all existing values for
        ``key``), "add" (append ``value``, keeping any existing values --
        multi-value qualifiers like /db_xref stay intact), or "remove"
        (drop ``key`` entirely). Features where the operation is a no-op
        (e.g. "remove" on a feature that never had that qualifier) are left
        untouched and excluded from the returned list.
        """
        if operation not in ("set", "add", "remove"):
            raise ValueError(f"unknown batch qualifier operation: {operation!r}")

        pairs: list[tuple[Feature, Feature]] = []
        for before in features:
            qualifiers = before.qualifiers.copy()
            if operation == "set":
                qualifiers.set_all(key, [value])
            elif operation == "add":
                qualifiers.add(key, value)
            elif operation == "remove":
                if not qualifiers.has(key):
                    continue
                qualifiers.remove_key(key)
            after = _copy_feature_with(before, qualifiers=qualifiers)
            pairs.append((before, after))

        return self._push_batch_update(
            pairs, f"Batch {operation} qualifier '{key}' on {len(pairs)} feature(s)"
        )

    def apply_template_to_features(
        self, features: list[Feature], template: AnnotationTemplate
    ) -> list[Feature]:
        """Applies an annotation template's type + common qualifiers to many
        features at once, as a single undo step. Empty template fields are
        left untouched on the target features (an empty "gene" in the
        template doesn't erase an existing gene qualifier)."""
        pairs: list[tuple[Feature, Feature]] = []
        for before in features:
            qualifiers = before.qualifiers.copy()
            if template.gene:
                qualifiers.set_all("gene", [template.gene])
            if template.product:
                qualifiers.set_all("product", [template.product])
            if template.note:
                qualifiers.set_all("note", [template.note])
            if template.transl_table:
                qualifiers.set_all("transl_table", [template.transl_table])
            for extra_key, extra_value in template.extra_qualifiers:
                qualifiers.set_all(extra_key, [extra_value])
            after = _copy_feature_with(
                before, type=template.feature_type or before.type, qualifiers=qualifiers
            )
            pairs.append((before, after))

        return self._push_batch_update(
            pairs, f"Apply template '{template.name}' to {len(pairs)} feature(s)"
        )

    def _push_batch_update(
        self, pairs: list[tuple[Feature, Feature]], description: str
    ) -> list[Feature]:
        if not pairs:
            return []
        repo = self._project_service.require_writable()
        commands: list[FeatureUpdateCommand] = []
        updated: list[Feature] = []
        for before, after in pairs:
            after.modified_at = utc_now()
            after.revision = before.revision + 1
            commands.append(FeatureUpdateCommand(repo, before, after))
            updated.append(after)
        batch = BatchCommand(list(commands), description)
        self._project_service.undo_stack.push(batch)
        self._project_service.log_audit(EventType.FEATURE_UPDATE, "batch", description)
        self._project_service.touch()
        return updated

    def delete_feature(self, feature: Feature) -> None:
        repo = self._project_service.require_writable()
        command = FeatureDeleteCommand(repo, feature)
        self._project_service.undo_stack.push(command)
        self._project_service.log_audit(
            EventType.FEATURE_DELETE, feature.id, f"Deleted {feature.type} feature"
        )
        self._project_service.touch()
