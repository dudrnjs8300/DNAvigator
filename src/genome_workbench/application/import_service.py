"""Import orchestration: format sniff -> adapter -> repository, with audit logging."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from genome_workbench.application.project_service import ProjectService
from genome_workbench.domain.events import EventType
from genome_workbench.domain.models import Alignment, Feature, MoleculeType, SequenceRecord
from genome_workbench.infrastructure.formats.alignment_adapter import read_alignment
from genome_workbench.infrastructure.formats.fasta_adapter import read_fasta
from genome_workbench.infrastructure.formats.genbank_adapter import read_genbank
from genome_workbench.infrastructure.formats.gff3_adapter import read_gff3
from genome_workbench.infrastructure.formats.issues import ImportIssue, ImportSeverity


@dataclass(slots=True)
class ImportResult:
    records: list[SequenceRecord] = field(default_factory=list)
    features_by_record_id: dict[str, list[Feature]] = field(default_factory=dict)
    issues: list[ImportIssue] = field(default_factory=list)


@dataclass(slots=True)
class AlignmentImportOutcome:
    alignments: list[Alignment] = field(default_factory=list)
    issues: list[ImportIssue] = field(default_factory=list)


class ImportService:
    def __init__(self, project_service: ProjectService) -> None:
        self._project_service = project_service

    def import_fasta(
        self, path: Path, molecule_type_hint: MoleculeType | None = None
    ) -> ImportResult:
        repo = self._project_service.require_writable()
        parsed = read_fasta(Path(path), molecule_type_hint=molecule_type_hint)
        repo.save_records_bulk(parsed.records)
        if parsed.records:
            self._project_service.log_audit(
                EventType.IMPORT,
                parsed.records[0].id,
                f"Imported {len(parsed.records)} record(s) from FASTA: {Path(path).name}",
            )
        self._project_service.touch()
        return ImportResult(records=parsed.records, issues=list(parsed.issues))

    def import_genbank(self, path: Path) -> ImportResult:
        repo = self._project_service.require_writable()
        parsed = read_genbank(Path(path))
        repo.save_records_bulk(parsed.records)
        for features in parsed.features_by_record_id.values():
            repo.save_features_bulk(features)
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

    def import_gff3(self, path: Path, external_fasta_path: Path | None = None) -> ImportResult:
        repo = self._project_service.require_writable()
        parsed = read_gff3(Path(path))
        issues = list(parsed.issues)

        if external_fasta_path is not None:
            fasta_result = read_fasta(Path(external_fasta_path))
            sequences_by_id = {r.display_id: r for r in fasta_result.records}
            for record in parsed.records:
                matched = sequences_by_id.pop(record.display_id, None)
                if matched is not None:
                    record.sequence = matched.sequence
                    record.checksum_sha256 = matched.checksum_sha256
                    record.molecule_type = matched.molecule_type
                    parsed.unmatched_seqids.discard(record.display_id)
            for leftover_id in sequences_by_id:
                issues.append(
                    ImportIssue(
                        ImportSeverity.WARNING,
                        "unmatched_fasta_record",
                        f"FASTA record '{leftover_id}' has no matching GFF3 seqid",
                    )
                )

        for seqid in parsed.unmatched_seqids:
            issues.append(
                ImportIssue(
                    ImportSeverity.WARNING,
                    "unmatched_seqid",
                    f"GFF3 seqid '{seqid}' has no sequence data (annotation-only)",
                )
            )

        repo.save_records_bulk(parsed.records)
        for features in parsed.features_by_record_id.values():
            repo.save_features_bulk(features)
        if parsed.records:
            self._project_service.log_audit(
                EventType.IMPORT,
                parsed.records[0].id,
                f"Imported {len(parsed.records)} record(s) from GFF3: {Path(path).name}",
            )
        self._project_service.touch()
        return ImportResult(
            records=parsed.records,
            features_by_record_id=parsed.features_by_record_id,
            issues=issues,
        )

    def import_alignment(self, path: Path) -> AlignmentImportOutcome:
        repo = self._project_service.require_writable()
        parsed = read_alignment(Path(path))
        for alignment in parsed.alignments:
            repo.save_alignment(alignment, parsed.sequences_by_alignment_id[alignment.id])
        if parsed.alignments:
            self._project_service.log_audit(
                EventType.IMPORT,
                parsed.alignments[0].id,
                f"Imported {len(parsed.alignments)} alignment(s) from {Path(path).name}",
            )
        self._project_service.touch()
        return AlignmentImportOutcome(alignments=parsed.alignments, issues=list(parsed.issues))
