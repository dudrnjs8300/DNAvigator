"""Builds BLAST+ subprocess argument lists. Never shell strings."""

from __future__ import annotations

from pathlib import Path

from genome_workbench.domain.blast_models import BlastSearchParameters
from genome_workbench.domain.models import MoleculeType

OUTFMT_SPEC = (
    "6 qseqid sseqid pident length mismatch gapopen "
    "qstart qend sstart send evalue bitscore "
    "qlen slen qcovhsp nident positive gaps frames "
    "qseq sseq stitle"
)


def build_makeblastdb_command(
    makeblastdb_path: Path,
    input_fasta: Path,
    molecule_type: MoleculeType,
    title: str,
    out_prefix: Path,
) -> list[str]:
    dbtype = "prot" if molecule_type == MoleculeType.PROTEIN else "nucl"
    return [
        str(makeblastdb_path),
        "-in",
        str(input_fasta),
        "-dbtype",
        dbtype,
        "-parse_seqids",
        "-title",
        title,
        "-out",
        str(out_prefix),
    ]


def build_blastdbcmd_info_command(
    blastdbcmd_path: Path, db_prefix: Path, molecule_type: MoleculeType
) -> list[str]:
    dbtype = "prot" if molecule_type == MoleculeType.PROTEIN else "nucl"
    return [str(blastdbcmd_path), "-db", str(db_prefix), "-dbtype", dbtype, "-info"]


def build_search_command(
    program_path: Path,
    query_fasta: Path,
    db_prefix: Path,
    params: BlastSearchParameters,
) -> list[str]:
    command = [
        str(program_path),
        "-query",
        str(query_fasta),
        "-db",
        str(db_prefix),
        "-outfmt",
        OUTFMT_SPEC,
        "-evalue",
        str(params.evalue),
        "-max_target_seqs",
        str(params.max_target_seqs),
        "-num_threads",
        str(max(1, params.threads)),
    ]
    return command
