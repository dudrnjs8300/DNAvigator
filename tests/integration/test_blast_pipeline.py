"""Exercises the real subprocess pipeline (command build -> run -> parse)
against mock BLAST+ executables (batch scripts), per spec 16.1's "mock BLAST
executable interaction" integration test category. Command construction,
subprocess execution, stdout capture, and tabular parsing are all real; only
the external tool itself is a stand-in for actual NCBI BLAST+.
"""

from pathlib import Path

import pytest

from genome_workbench.domain.blast_models import BlastProgram, BlastSearchParameters
from genome_workbench.domain.models import MoleculeType
from genome_workbench.infrastructure.blast.command_builder import build_search_command
from genome_workbench.infrastructure.blast.database_manager import create_database
from genome_workbench.infrastructure.blast.parser import parse_tabular_output
from genome_workbench.infrastructure.blast.runner import run_search_to_file

FAKE_BLAST_DIR = Path(__file__).parent.parent / "fixtures" / "fake_blast"


@pytest.fixture
def source_fasta(tmp_path: Path) -> Path:
    path = tmp_path / "source.fasta"
    path.write_text(
        ">clean_id description one\n"
        "ACGTACGTACGTACGTACGT\n"
        ">bad|id|with|pipes another record\n"
        "TTTTGGGGCCCCAAAATTTT\n"
    )
    return path


def test_create_database_with_mock_makeblastdb(tmp_path: Path, source_fasta: Path):
    work_dir = tmp_path / "db_work"
    database = create_database(
        source_fasta=source_fasta,
        molecule_type=MoleculeType.DNA,
        name="test_db",
        work_dir=work_dir,
        makeblastdb_path=FAKE_BLAST_DIR / "makeblastdb.bat",
        blastdbcmd_path=FAKE_BLAST_DIR / "blastdbcmd.bat",
    )
    assert database.sequence_count == 3
    assert database.molecule_type == MoleculeType.DNA
    assert "clean_id" in database.id_map
    # the pipe-containing id must have been replaced with a safe generated id
    unsafe_original_id = "bad|id|with|pipes"
    assert unsafe_original_id in database.id_map.values()
    assert unsafe_original_id not in database.id_map
    assert (work_dir / "db_manifest.json").exists()
    assert (work_dir / "normalized.fasta").exists()


def test_run_search_and_parse_with_mock_blastn(tmp_path: Path):
    params = BlastSearchParameters(
        program=BlastProgram.BLASTN, evalue=1e-5, max_target_seqs=10, threads=1
    )
    query_fasta = tmp_path / "query.fasta"
    query_fasta.write_text(">QUERY1\nACGTACGTACGT\n")

    command = build_search_command(
        FAKE_BLAST_DIR / "blastn.bat", query_fasta, tmp_path / "db" / "db", params
    )
    raw_output_path = tmp_path / "raw_output.tsv"
    result = run_search_to_file(command, raw_output_path)
    assert result.exit_code == 0
    assert raw_output_path.exists()

    parsed = parse_tabular_output(raw_output_path.read_text())
    assert parsed.issues == []
    assert len(parsed.hits) == 1
    hit = parsed.hits[0]
    assert hit.subject_id == "fake_subject_1"
    assert hit.subject_title == "Fake subject protein one"
    assert hit.best_identity == pytest.approx(97.5)
