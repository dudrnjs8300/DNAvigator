"""Exercises the BLAST pipeline against a REAL NCBI BLAST+ installation when
one is available on the machine running the tests (auto-detected the same
way the application does). Automatically skipped otherwise -- CI and most
dev machines won't have BLAST+ installed, and tests/integration/
test_blast_pipeline.py already covers the same code paths against a mock.

This closes the "never verified against a real binary" gap noted in
docs/RELEASE_TEST_REPORT.md (AT-06/AT-07): it was run once against a real
NCBI BLAST+ 2.17.0 install (blastn + blastp, database creation, coordinate
mapping, and annotation application all verified end to end).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from genome_workbench.application.annotation_service import AnnotationService
from genome_workbench.application.blast_service import BlastService
from genome_workbench.application.import_service import ImportService
from genome_workbench.application.project_service import ProjectService
from genome_workbench.domain.blast_models import BlastProgram, BlastSearchParameters
from genome_workbench.domain.models import MoleculeType
from genome_workbench.domain.qualifiers import QualifierSet
from genome_workbench.infrastructure.blast import detector

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"

_installation = detector.detect_installation()
_HAS_REAL_BLAST = set(detector.REQUIRED_EXECUTABLES) <= set(_installation.executables)

pytestmark = pytest.mark.skipif(
    not _HAS_REAL_BLAST,
    reason="No real NCBI BLAST+ installation auto-detected on this machine",
)


def test_real_blastn_self_hit_and_apply_as_annotation(tmp_path: Path):
    project_service = ProjectService()
    import_service = ImportService(project_service)
    annotation_service = AnnotationService(project_service)
    blast_service = BlastService(project_service, work_dir=tmp_path / "blast_work")

    project_service.create_new(tmp_path / "verify.gwbproj", "Real BLAST test")
    record = import_service.import_fasta(FIXTURES_DIR / "simple_linear.fasta").records[0]

    db = blast_service.create_database(
        _installation, FIXTURES_DIR / "simple_linear.fasta", MoleculeType.DNA, "real_nt_db"
    )
    assert db.sequence_count == 1

    query_fasta = tmp_path / "query.fasta"
    query_fasta.write_text(f">fragment\n{record.sequence[0:300]}\n", encoding="utf-8")

    result = blast_service.run_search(
        _installation,
        db,
        BlastProgram.BLASTN,
        query_fasta,
        BlastSearchParameters(program=BlastProgram.BLASTN, evalue=10.0, max_target_seqs=5),
        query_source_record_id=record.id,
        query_source_end0=300,
    )
    assert len(result.hits) >= 1
    hsp = result.hits[0].hsps[0]
    assert hsp.identity_pct >= 99.0
    assert hsp.query_coverage_pct >= 99.0

    feature = blast_service.apply_hit_as_annotation(
        annotation_service,
        record,
        result,
        result.hits[0],
        hsp,
        "misc_feature",
        QualifierSet.from_pairs([("note", "real BLAST+ verification hit")]),
    )
    assert (feature.start0, feature.end0) == (0, 300)

    project_service.close()


def test_real_blastp_self_hit(tmp_path: Path):
    project_service = ProjectService()
    blast_service = BlastService(project_service, work_dir=tmp_path / "blast_work")

    db = blast_service.create_database(
        _installation, FIXTURES_DIR / "protein_set.faa", MoleculeType.PROTEIN, "real_prot_db"
    )
    assert db.sequence_count == 3

    query_fasta = tmp_path / "query.faa"
    query_fasta.write_text(">query_prot\nMKVLATGCDEFGHIK\n", encoding="utf-8")

    result = blast_service.run_search(
        _installation,
        db,
        BlastProgram.BLASTP,
        query_fasta,
        BlastSearchParameters(program=BlastProgram.BLASTP, evalue=10.0, max_target_seqs=5),
    )
    assert len(result.hits) >= 1
    assert result.hits[0].subject_id == "protein_1"
