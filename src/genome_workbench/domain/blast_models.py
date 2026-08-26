"""BLAST domain entities (spec 5.2). No subprocess/Qt/file-IO here."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from genome_workbench.domain.models import MoleculeType, new_id, utc_now


class BlastProgram(str, Enum):
    BLASTN = "blastn"
    BLASTP = "blastp"
    BLASTX = "blastx"
    TBLASTN = "tblastn"


def suggest_program(
    query_molecule_type: MoleculeType, database_molecule_type: MoleculeType
) -> BlastProgram:
    if (
        query_molecule_type == MoleculeType.PROTEIN
        and database_molecule_type == MoleculeType.PROTEIN
    ):
        return BlastProgram.BLASTP
    if (
        query_molecule_type == MoleculeType.PROTEIN
        and database_molecule_type != MoleculeType.PROTEIN
    ):
        return BlastProgram.TBLASTN
    if (
        query_molecule_type != MoleculeType.PROTEIN
        and database_molecule_type == MoleculeType.PROTEIN
    ):
        return BlastProgram.BLASTX
    return BlastProgram.BLASTN


@dataclass(slots=True)
class BlastInstallation:
    directory: str | None
    executables: dict[str, str] = field(default_factory=dict)  # name -> absolute path
    versions: dict[str, str] = field(default_factory=dict)

    def has(self, name: str) -> bool:
        return name in self.executables

    def is_fully_installed(self) -> bool:
        required = ("makeblastdb", "blastdbcmd", "blastn", "blastp", "blastx", "tblastn")
        return all(name in self.executables for name in required)


@dataclass(slots=True)
class BlastDatabase:
    id: str = field(default_factory=new_id)
    name: str = ""
    molecule_type: MoleculeType = MoleculeType.DNA
    path_prefix: str = ""
    source_path: str = ""
    source_checksum: str = ""
    sequence_count: int = 0
    created_at: str = field(default_factory=utc_now)
    id_map: dict[str, str] = field(default_factory=dict)  # safe_id -> original_id


@dataclass(slots=True)
class BlastSearchParameters:
    program: BlastProgram
    evalue: float = 1e-5
    max_target_seqs: int = 50
    min_identity: float = 0.0
    min_query_coverage: float = 0.0
    threads: int = 4


@dataclass(slots=True)
class BlastHsp:
    query_start0: int
    query_end0: int
    subject_start0: int
    subject_end0: int
    subject_strand: int
    identity_pct: float
    align_length: int
    mismatches: int
    gap_opens: int
    evalue: float
    bitscore: float
    query_length: int
    subject_length: int
    query_coverage_pct: float
    query_seq: str
    subject_seq: str
    frames: str = ""


@dataclass(slots=True)
class BlastHit:
    subject_id: str
    subject_title: str
    hsps: list[BlastHsp] = field(default_factory=list)

    @property
    def best_identity(self) -> float:
        return max((h.identity_pct for h in self.hsps), default=0.0)

    @property
    def best_evalue(self) -> float:
        return min((h.evalue for h in self.hsps), default=float("inf"))

    @property
    def best_bitscore(self) -> float:
        return max((h.bitscore for h in self.hsps), default=0.0)

    @property
    def best_query_coverage(self) -> float:
        return max((h.query_coverage_pct for h in self.hsps), default=0.0)


@dataclass(slots=True)
class BlastSearchResult:
    program: BlastProgram
    database_id: str
    query_checksum: str
    parameters: BlastSearchParameters
    hits: list[BlastHit] = field(default_factory=list)
    raw_output_path: str = ""
    executable_version: str = ""
    # Genomic origin of the submitted query, so a hit's query-relative HSP
    # coordinates can be mapped back onto the source record for annotation.
    query_source_record_id: str = ""
    query_source_start0: int = 0
    query_source_end0: int = 0
    query_source_strand: int = 1


def map_hsp_to_genome_location(
    search_result: BlastSearchResult, hsp: BlastHsp
) -> tuple[int, int, int]:
    """Map an HSP's query-relative coordinates back onto the source genome.

    Returns ``(genome_start0, genome_end0, genome_strand)``. If the submitted
    query was itself a reverse-complemented extraction (``query_source_strand
    == -1``), the query-relative offset is mirrored before being placed back
    onto the forward genome coordinate system.
    """
    if search_result.query_source_strand == 1:
        genome_start0 = search_result.query_source_start0 + hsp.query_start0
        genome_end0 = search_result.query_source_start0 + hsp.query_end0
    else:
        genome_end0 = search_result.query_source_end0 - hsp.query_start0
        genome_start0 = search_result.query_source_end0 - hsp.query_end0
    genome_strand = search_result.query_source_strand * hsp.subject_strand
    return genome_start0, genome_end0, genome_strand
