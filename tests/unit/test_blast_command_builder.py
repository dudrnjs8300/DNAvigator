from pathlib import Path

from genome_workbench.domain.blast_models import BlastProgram, BlastSearchParameters
from genome_workbench.domain.models import MoleculeType
from genome_workbench.infrastructure.blast.command_builder import (
    build_blastdbcmd_info_command,
    build_makeblastdb_command,
    build_search_command,
)


def test_makeblastdb_command_nucleotide():
    cmd = build_makeblastdb_command(
        Path("makeblastdb"), Path("in.fasta"), MoleculeType.DNA, "mydb", Path("out/mydb")
    )
    assert cmd[0] == "makeblastdb"
    assert "-dbtype" in cmd
    assert cmd[cmd.index("-dbtype") + 1] == "nucl"
    assert "-parse_seqids" in cmd
    assert "in.fasta" in cmd


def test_makeblastdb_command_protein():
    cmd = build_makeblastdb_command(
        Path("makeblastdb"), Path("in.faa"), MoleculeType.PROTEIN, "mydb", Path("out/mydb")
    )
    assert cmd[cmd.index("-dbtype") + 1] == "prot"


def test_blastdbcmd_info_command():
    cmd = build_blastdbcmd_info_command(Path("blastdbcmd"), Path("out/mydb"), MoleculeType.DNA)
    assert "-info" in cmd
    assert cmd[cmd.index("-dbtype") + 1] == "nucl"


def test_search_command_contains_evalue_and_threads():
    params = BlastSearchParameters(
        program=BlastProgram.BLASTN, evalue=1e-10, max_target_seqs=25, threads=2
    )
    cmd = build_search_command(Path("blastn"), Path("query.fasta"), Path("out/mydb"), params)
    assert cmd[cmd.index("-evalue") + 1] == "1e-10"
    assert cmd[cmd.index("-max_target_seqs") + 1] == "25"
    assert cmd[cmd.index("-num_threads") + 1] == "2"
    assert "-outfmt" in cmd


def test_search_command_is_never_a_shell_string():
    params = BlastSearchParameters(program=BlastProgram.BLASTN)
    cmd = build_search_command(Path("blastn"), Path("query.fasta"), Path("out/mydb"), params)
    assert isinstance(cmd, list)
    assert all(isinstance(part, str) for part in cmd)
