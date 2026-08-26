"""Builds a validated NCBI BLAST database from a FASTA source (spec 11.2).

Steps: normalize/validate sequence IDs (writing a safe-ID mapping for any
ID containing characters ``-parse_seqids`` chokes on), run ``makeblastdb``,
validate with ``blastdbcmd -info``, write a manifest. The actual subprocess
calls are blocking; callers run this off the UI thread.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from Bio import SeqIO

from genome_workbench.domain.blast_models import BlastDatabase
from genome_workbench.domain.models import MoleculeType
from genome_workbench.infrastructure.blast.command_builder import (
    build_blastdbcmd_info_command,
    build_makeblastdb_command,
)
from genome_workbench.infrastructure.blast.runner import run_command_or_raise
from genome_workbench.infrastructure.filesystem.checksums import sha256_of_file

_SAFE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]+$")
_SEQUENCE_COUNT_PATTERN = re.compile(r"([\d,]+)\s+sequences", re.IGNORECASE)


class DatabaseCreationError(RuntimeError):
    pass


def normalize_fasta_for_blastdb(source_fasta: Path, destination_fasta: Path) -> dict[str, str]:
    """Write a normalized copy of ``source_fasta`` and return safe_id -> original_id."""
    records = list(SeqIO.parse(str(source_fasta), "fasta"))
    if not records:
        raise DatabaseCreationError(f"no FASTA records found in {source_fasta}")

    id_map: dict[str, str] = {}
    seen_ids: set[str] = set()
    for index, record in enumerate(records):
        original_id = record.id
        is_safe = bool(_SAFE_ID_PATTERN.match(original_id))
        is_duplicate = original_id in seen_ids
        if is_safe and not is_duplicate:
            id_map[original_id] = original_id
        else:
            safe_id = f"seq_{index + 1:06d}"
            id_map[safe_id] = original_id
            record.description = (
                f"{safe_id} {record.description}" if record.description != original_id else safe_id
            )
            record.id = safe_id
        seen_ids.add(original_id)

    SeqIO.write(records, str(destination_fasta), "fasta")
    return id_map


def _extract_sequence_count(blastdbcmd_info_output: str) -> int:
    match = _SEQUENCE_COUNT_PATTERN.search(blastdbcmd_info_output)
    if not match:
        return 0
    return int(match.group(1).replace(",", ""))


def create_database(
    source_fasta: Path,
    molecule_type: MoleculeType,
    name: str,
    work_dir: Path,
    makeblastdb_path: Path,
    blastdbcmd_path: Path,
) -> BlastDatabase:
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    normalized_fasta = work_dir / "normalized.fasta"
    id_map = normalize_fasta_for_blastdb(source_fasta, normalized_fasta)
    checksum = sha256_of_file(source_fasta)

    db_prefix = work_dir / "db"
    makeblastdb_command = build_makeblastdb_command(
        makeblastdb_path, normalized_fasta, molecule_type, name, db_prefix
    )
    run_command_or_raise(makeblastdb_command)

    info_command = build_blastdbcmd_info_command(blastdbcmd_path, db_prefix, molecule_type)
    info_result = run_command_or_raise(info_command)
    sequence_count = _extract_sequence_count(info_result.stdout)

    database = BlastDatabase(
        name=name,
        molecule_type=molecule_type,
        path_prefix=str(db_prefix),
        source_path=str(source_fasta),
        source_checksum=checksum,
        sequence_count=sequence_count,
        id_map=id_map,
    )

    manifest = {
        "schema_version": 1,
        "database_id": database.id,
        "name": database.name,
        "molecule_type": database.molecule_type.value,
        "source_path": database.source_path,
        "source_checksum": database.source_checksum,
        "sequence_count": database.sequence_count,
        "created_at": database.created_at,
        "id_map": database.id_map,
    }
    (work_dir / "db_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return database
