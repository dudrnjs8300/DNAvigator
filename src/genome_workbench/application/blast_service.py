"""Orchestrates BLAST installation detection, database creation, search
execution, and (only after explicit user confirmation) annotation creation
from a chosen hit. Every subprocess call here is blocking — the UI layer runs
these through a worker thread (ui/workers/callable_worker.py), never on the
Qt UI thread directly.
"""

from __future__ import annotations

import json
from pathlib import Path

from genome_workbench.application.annotation_service import AnnotationService
from genome_workbench.application.project_service import ProjectService
from genome_workbench.domain.blast_models import (
    BlastDatabase,
    BlastHit,
    BlastHsp,
    BlastInstallation,
    BlastProgram,
    BlastSearchParameters,
    BlastSearchResult,
    map_hsp_to_genome_location,
)
from genome_workbench.domain.events import EventType
from genome_workbench.domain.models import MoleculeType, Provenance, ProvenanceKind, SequenceRecord
from genome_workbench.domain.qualifiers import QualifierSet
from genome_workbench.infrastructure.blast import database_manager, detector
from genome_workbench.infrastructure.blast.command_builder import build_search_command
from genome_workbench.infrastructure.blast.parser import parse_tabular_output
from genome_workbench.infrastructure.blast.runner import run_search_to_file
from genome_workbench.infrastructure.filesystem.checksums import sha256_of_file
from genome_workbench.infrastructure.filesystem.paths import app_data_dir


def blast_work_dir() -> Path:
    directory = app_data_dir() / "blast"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


class BlastService:
    """Holds the in-session database catalog. Applied-annotation evidence is
    persisted durably via Provenance rows (see AnnotationService); the raw
    hit/HSP list of a completed search is intentionally session-scoped, kept
    only long enough for the user to review results and apply them.
    """

    def __init__(self, project_service: ProjectService, work_dir: Path | None = None) -> None:
        self._project_service = project_service
        self._work_dir = work_dir or blast_work_dir()
        self._work_dir.mkdir(parents=True, exist_ok=True)
        self._databases: dict[str, BlastDatabase] = {}
        self._load_catalog()

    # -- Installation --------------------------------------------------------

    def detect_installation(self, search_dir: Path | None = None) -> BlastInstallation:
        return detector.detect_installation(search_dir)

    # -- Database catalog ------------------------------------------------------

    def _catalog_path(self) -> Path:
        return self._work_dir / "catalog.json"

    def _load_catalog(self) -> None:
        path = self._catalog_path()
        if not path.exists():
            return
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        for entry in raw:
            db = BlastDatabase(
                id=entry["id"],
                name=entry["name"],
                molecule_type=MoleculeType(entry["molecule_type"]),
                path_prefix=entry["path_prefix"],
                source_path=entry["source_path"],
                source_checksum=entry["source_checksum"],
                sequence_count=entry["sequence_count"],
                created_at=entry["created_at"],
                id_map=entry.get("id_map", {}),
            )
            self._databases[db.id] = db

    def _save_catalog(self) -> None:
        entries = [
            {
                "id": db.id,
                "name": db.name,
                "molecule_type": db.molecule_type.value,
                "path_prefix": db.path_prefix,
                "source_path": db.source_path,
                "source_checksum": db.source_checksum,
                "sequence_count": db.sequence_count,
                "created_at": db.created_at,
                "id_map": db.id_map,
            }
            for db in self._databases.values()
        ]
        self._catalog_path().write_text(json.dumps(entries, indent=2), encoding="utf-8")

    @property
    def work_dir(self) -> Path:
        return self._work_dir

    def list_databases(self) -> list[BlastDatabase]:
        return list(self._databases.values())

    def create_database(
        self,
        installation: BlastInstallation,
        source_fasta: Path,
        molecule_type: MoleculeType,
        name: str,
    ) -> BlastDatabase:
        if (
            "makeblastdb" not in installation.executables
            or "blastdbcmd" not in installation.executables
        ):
            raise RuntimeError(
                "makeblastdb/blastdbcmd are not available in this BLAST installation"
            )
        work_dir = self._work_dir / "databases" / name.replace(" ", "_")
        database = database_manager.create_database(
            source_fasta=source_fasta,
            molecule_type=molecule_type,
            name=name,
            work_dir=work_dir,
            makeblastdb_path=Path(installation.executables["makeblastdb"]),
            blastdbcmd_path=Path(installation.executables["blastdbcmd"]),
        )
        self._databases[database.id] = database
        self._save_catalog()
        if self._project_service.is_open:
            self._project_service.log_audit(
                EventType.BLAST_DATABASE_CREATE,
                database.id,
                f"Created BLAST database '{name}' ({database.sequence_count} sequences)",
            )
        return database

    def remove_database(self, database_id: str) -> None:
        self._databases.pop(database_id, None)
        self._save_catalog()

    # -- Search ----------------------------------------------------------------

    def run_search(
        self,
        installation: BlastInstallation,
        database: BlastDatabase,
        program: BlastProgram,
        query_fasta: Path,
        params: BlastSearchParameters,
        query_source_record_id: str = "",
        query_source_start0: int = 0,
        query_source_end0: int = 0,
        query_source_strand: int = 1,
    ) -> BlastSearchResult:
        if program.value not in installation.executables:
            raise RuntimeError(
                f"{program.value} executable is not available in this BLAST installation"
            )
        program_path = Path(installation.executables[program.value])
        command = build_search_command(
            program_path, query_fasta, Path(database.path_prefix), params
        )
        raw_output_path = self._work_dir / "jobs" / f"{database.id}_{program.value}.tsv"
        result = run_search_to_file(command, raw_output_path)
        parsed = parse_tabular_output(result.stdout)
        _translate_ids_back(parsed.hits, database.id_map)
        _apply_display_filters(parsed.hits, params)

        search_result = BlastSearchResult(
            program=program,
            database_id=database.id,
            query_checksum=sha256_of_file(query_fasta),
            parameters=params,
            hits=parsed.hits,
            raw_output_path=str(raw_output_path),
            executable_version=installation.versions.get(program.value, ""),
            query_source_record_id=query_source_record_id,
            query_source_start0=query_source_start0,
            query_source_end0=query_source_end0,
            query_source_strand=query_source_strand,
        )
        if self._project_service.is_open:
            self._project_service.log_audit(
                EventType.BLAST_RUN,
                database.id,
                f"{program.value} vs '{database.name}': {len(parsed.hits)} hit(s)",
            )
        return search_result

    # -- Annotation application --------------------------------------------------

    def apply_hit_as_annotation(
        self,
        annotation_service: AnnotationService,
        target_record: SequenceRecord,
        search_result: BlastSearchResult,
        hit: BlastHit,
        hsp: BlastHsp,
        feature_type: str,
        qualifiers: QualifierSet,
    ):
        genome_start0, genome_end0, genome_strand = map_hsp_to_genome_location(search_result, hsp)
        provenance = Provenance(
            kind=ProvenanceKind.BLAST,
            tool_name=search_result.program.value,
            tool_version=search_result.executable_version,
            database_id=search_result.database_id,
            query_checksum=search_result.query_checksum,
            parameters_json=json.dumps(
                {
                    "evalue": search_result.parameters.evalue,
                    "max_target_seqs": search_result.parameters.max_target_seqs,
                    "threads": search_result.parameters.threads,
                }
            ),
            subject_id=hit.subject_id,
            identity=hsp.identity_pct,
            query_coverage=hsp.query_coverage_pct,
            evalue=hsp.evalue,
            bitscore=hsp.bitscore,
            raw_result_ref=search_result.raw_output_path,
        )
        start_1based, end_1based = genome_start0 + 1, genome_end0
        feature = annotation_service.create_simple_feature(
            target_record,
            start_1based,
            end_1based,
            genome_strand,
            feature_type,
            qualifiers,
            provenance=provenance,
        )
        if self._project_service.is_open:
            self._project_service.log_audit(
                EventType.BLAST_ANNOTATION_APPLY,
                feature.id,
                f"Applied BLAST hit '{hit.subject_id}' as {feature_type} at "
                f"{start_1based}..{end_1based}",
            )
        return feature


def _translate_ids_back(hits: list[BlastHit], id_map: dict[str, str]) -> None:
    for hit in hits:
        original = id_map.get(hit.subject_id)
        if original and original != hit.subject_id:
            hit.subject_id = original


def _apply_display_filters(hits: list[BlastHit], params: BlastSearchParameters) -> None:
    if params.min_identity <= 0 and params.min_query_coverage <= 0:
        return
    for hit in list(hits):
        hit.hsps = [
            h
            for h in hit.hsps
            if h.identity_pct >= params.min_identity
            and h.query_coverage_pct >= params.min_query_coverage
        ]
    hits[:] = [hit for hit in hits if hit.hsps]
