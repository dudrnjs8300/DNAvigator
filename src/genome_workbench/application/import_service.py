"""Import orchestration: format sniff -> adapter -> repository, with audit logging."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from genome_workbench.application.project_service import ProjectService
from genome_workbench.domain.events import EventType
from genome_workbench.domain.models import Feature, MoleculeType, SequenceRecord
from genome_workbench.infrastructure.formats.fasta_adapter import read_fasta
from genome_workbench.infrastructure.formats.genbank_adapter import read_genbank
from genome_workbench.infrastructure.formats.issues import ImportIssue


@dataclass(slots=True)
class ImportResult:
    records: list[SequenceRecord] = field(default_factory=list)
    features_by_record_id: dict[str, list[Feature]] = field(default_factory=dict)
    issues: list[ImportIssue] = field(default_factory=list)


class ImportService:
    def __init__(self, project_service: ProjectService) -> None:
        self._project_service = project_service

    def import_fasta(
        self, path: Path, molecule_type_hint: MoleculeType | None = None
    ) -> ImportResult:
        repo = self._project_service.get_repository()
        parsed = read_fasta(Path(path), molecule_type_hint=molecule_type_hint)
        for record in parsed.records:
            repo.save_record(record)
        if parsed.records:
            self._project_service.log_audit(
                EventType.IMPORT,
                parsed.records[0].id,
                f"Imported {len(parsed.records)} record(s) from FASTA: {Path(path).name}",
            )
        self._project_service.touch()
        return ImportResult(records=parsed.records, issues=list(parsed.issues))

    def import_genbank(self, path: Path) -> ImportResult:
        repo = self._project_service.get_repository()
        parsed = read_genbank(Path(path))
        for record in parsed.records:
            repo.save_record(record)
        for features in parsed.features_by_record_id.values():
            for feature in features:
                repo.save_feature(feature)
        if parsed.records:
            self._project_service.log_audit(
                EventType.IMPORT,
                parsed.records[0].id,
                f"Imported {len(parsed.records)} record(s) from GenBank: {Path(path).name}",
            )
        self._project_service.touch()
        return ImportResult(
            records=parsed.records,
            features_by_record_id=parsed.features_by_record_id,
            issues=list(parsed.issues),
        )
