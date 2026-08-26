"""Export orchestration: write -> reimport -> semantic compare -> atomic move.

Never leaves a partially written or unvalidated file at the user's chosen
destination: validation happens against the temp file, and only a clean
reimport comparison allows the atomic replace to happen.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from genome_workbench.application.project_service import ProjectService
from genome_workbench.domain.events import EventType
from genome_workbench.domain.models import Feature, SequenceRecord
from genome_workbench.infrastructure.filesystem.atomic_write import write_atomic
from genome_workbench.infrastructure.formats.genbank_adapter import read_genbank, write_genbank
from genome_workbench.infrastructure.formats.gff3_adapter import read_gff3, write_gff3
from genome_workbench.infrastructure.formats.semantic_compare import (
    DiffSeverity,
    SemanticDiff,
    compare_semantic,
)


class ExportValidationError(RuntimeError):
    def __init__(self, diffs: list[SemanticDiff]) -> None:
        self.diffs = diffs
        messages = "; ".join(f"[{d.code}] {d.message}" for d in diffs)
        super().__init__(f"export failed semantic round-trip validation: {messages}")


@dataclass(slots=True)
class ExportResult:
    destination: Path
    diffs: list[SemanticDiff] = field(default_factory=list)

    @property
    def warnings(self) -> list[SemanticDiff]:
        return [d for d in self.diffs if d.severity == DiffSeverity.WARNING]


class ExportService:
    def __init__(self, project_service: ProjectService) -> None:
        self._project_service = project_service

    def export_genbank(
        self,
        records: list[SequenceRecord],
        features_by_record_id: dict[str, list[Feature]],
        destination: Path,
        genetic_code: int = 11,
    ) -> ExportResult:
        destination = Path(destination)
        captured_diffs: list[SemanticDiff] = []

        def write_and_validate(temp_path: Path) -> None:
            write_genbank(records, features_by_record_id, temp_path)
            reimport = read_genbank(temp_path)
            diffs = compare_semantic(
                records,
                features_by_record_id,
                reimport.records,
                reimport.features_by_record_id,
                genetic_code=genetic_code,
            )
            captured_diffs.extend(diffs)
            errors = [d for d in diffs if d.severity == DiffSeverity.ERROR]
            if errors:
                raise ExportValidationError(errors)

        write_atomic(destination, write_and_validate)

        if self._project_service.is_open:
            self._project_service.log_audit(
                EventType.EXPORT,
                records[0].id if records else "",
                f"Exported {len(records)} record(s) to GenBank: {destination.name}",
            )
        return ExportResult(destination=destination, diffs=captured_diffs)

    def export_gff3(
        self,
        records: list[SequenceRecord],
        features_by_record_id: dict[str, list[Feature]],
        destination: Path,
        embed_fasta: bool = True,
        genetic_code: int = 11,
    ) -> ExportResult:
        destination = Path(destination)
        captured_diffs: list[SemanticDiff] = []

        def write_and_validate(temp_path: Path) -> None:
            write_gff3(records, features_by_record_id, temp_path, embed_fasta=embed_fasta)
            reimport = read_gff3(temp_path)
            if not embed_fasta:
                # sequence data is intentionally not written in this mode; supply the
                # originals so the comparison validates annotations, not a sequence
                # mismatch we already know is expected.
                for original, reimported in zip(records, reimport.records, strict=False):
                    reimported.sequence = original.sequence
                    reimported.checksum_sha256 = original.checksum_sha256
                    reimported.molecule_type = original.molecule_type
                    reimported.topology = original.topology
            diffs = compare_semantic(
                records,
                features_by_record_id,
                reimport.records,
                reimport.features_by_record_id,
                genetic_code=genetic_code,
            )
            captured_diffs.extend(diffs)
            errors = [d for d in diffs if d.severity == DiffSeverity.ERROR]
            if errors:
                raise ExportValidationError(errors)

        write_atomic(destination, write_and_validate)

        if self._project_service.is_open:
            self._project_service.log_audit(
                EventType.EXPORT,
                records[0].id if records else "",
                f"Exported {len(records)} record(s) to GFF3: {destination.name}",
            )
        return ExportResult(destination=destination, diffs=captured_diffs)
