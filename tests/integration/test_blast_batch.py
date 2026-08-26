"""Batch BLAST: one search per query (e.g. one per selected feature), run
sequentially via BlastService.run_batch_search, against the mock BLAST+
executables (spec 16.1's "mock BLAST executable interaction" category --
the same fixtures test_blast_pipeline.py uses).

Also a regression test for a real bug this feature surfaced: run_search's
raw output path used to be keyed only on database+program, so back-to-back
searches against the same database would silently overwrite each other's
raw result file -- by the time a batch finished, every earlier result's
Provenance.raw_result_ref pointed at the last query's output.
"""

from __future__ import annotations

import threading
from pathlib import Path

from genome_workbench.application.blast_service import BlastService
from genome_workbench.application.project_service import ProjectService
from genome_workbench.domain.blast_models import (
    BlastInstallation,
    BlastProgram,
    BlastSearchParameters,
)
from genome_workbench.domain.models import MoleculeType
from genome_workbench.infrastructure.blast.detector import REQUIRED_EXECUTABLES

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"
FAKE_BLAST_DIR = FIXTURES_DIR / "fake_blast"


def _installation() -> BlastInstallation:
    return BlastInstallation(
        directory=str(FAKE_BLAST_DIR),
        executables={name: str(FAKE_BLAST_DIR / f"{name}.bat") for name in REQUIRED_EXECUTABLES},
        versions={name: "fake 1.0" for name in REQUIRED_EXECUTABLES},
    )


def _setup(tmp_path: Path):
    project_service = ProjectService()
    project_service.create_new(tmp_path / "p.gwbproj", "P")
    blast_service = BlastService(project_service, work_dir=tmp_path / "blast_work")
    db_source = tmp_path / "db_source.fasta"
    db_source.write_text(">subject1\nACGTACGTACGTACGTACGT\n", encoding="utf-8")
    database = blast_service.create_database(
        _installation(), db_source, MoleculeType.DNA, "test_db"
    )
    return project_service, blast_service, database


def _write_query(tmp_path: Path, name: str, sequence: str = "ACGTACGTACGT") -> Path:
    path = tmp_path / f"{name}.fasta"
    path.write_text(f">{name}\n{sequence}\n", encoding="utf-8")
    return path


def test_batch_search_returns_one_result_per_query_attributed_to_feature_id(tmp_path: Path):
    _project_service, blast_service, database = _setup(tmp_path)
    queries = [
        ("feature-1", _write_query(tmp_path, "q1"), "rec1", 0, 300, 1),
        ("feature-2", _write_query(tmp_path, "q2"), "rec1", 400, 700, 1),
        ("feature-3", _write_query(tmp_path, "q3"), "rec1", 800, 1000, -1),
    ]
    params = BlastSearchParameters(program=BlastProgram.BLASTN, evalue=10.0, max_target_seqs=5)

    results = blast_service.run_batch_search(
        _installation(), database, BlastProgram.BLASTN, queries, params
    )

    assert [feature_id for feature_id, _result in results] == [
        "feature-1",
        "feature-2",
        "feature-3",
    ]
    for _feature_id, result in results:
        assert len(result.hits) == 1
        assert result.hits[0].subject_id == "fake_subject_1"


def test_batch_search_results_have_distinct_raw_output_paths(tmp_path: Path):
    """Regression test: each query's raw output file must be its own file,
    not silently overwritten by the next query in the batch."""
    _project_service, blast_service, database = _setup(tmp_path)
    queries = [
        ("feature-1", _write_query(tmp_path, "q1", "AAAACCCCGGGG"), "rec1", 0, 12, 1),
        ("feature-2", _write_query(tmp_path, "q2", "TTTTGGGGCCCC"), "rec1", 12, 24, 1),
    ]
    params = BlastSearchParameters(program=BlastProgram.BLASTN, evalue=10.0, max_target_seqs=5)

    results = blast_service.run_batch_search(
        _installation(), database, BlastProgram.BLASTN, queries, params
    )

    raw_paths = {result.raw_output_path for _feature_id, result in results}
    assert len(raw_paths) == 2  # not collapsed into a single shared file
    for path_str in raw_paths:
        assert Path(path_str).exists()


def test_batch_search_stops_between_queries_once_cancelled(tmp_path: Path):
    _project_service, blast_service, database = _setup(tmp_path)
    queries = [
        (f"feature-{i}", _write_query(tmp_path, f"q{i}"), "rec1", i * 10, i * 10 + 5, 1)
        for i in range(5)
    ]
    params = BlastSearchParameters(program=BlastProgram.BLASTN, evalue=10.0, max_target_seqs=5)
    cancel_event = threading.Event()
    cancel_event.set()  # cancelled before the batch even starts

    results = blast_service.run_batch_search(
        _installation(), database, BlastProgram.BLASTN, queries, params, cancel_event=cancel_event
    )

    assert results == []


def test_batch_search_empty_query_list_returns_empty(tmp_path: Path):
    _project_service, blast_service, database = _setup(tmp_path)
    params = BlastSearchParameters(program=BlastProgram.BLASTN, evalue=10.0, max_target_seqs=5)
    assert (
        blast_service.run_batch_search(_installation(), database, BlastProgram.BLASTN, [], params)
        == []
    )
