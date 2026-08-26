"""End-to-end batch BLAST through the real UI: select multiple features in
the Feature Table, run BLAST against all of them at once, review results in
BatchBlastResultsDialog, and apply one hit -- same "never auto-apply, always
require explicit confirmation" rule as a single BLAST search (spec 11.9).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from genome_workbench.domain.blast_models import BlastInstallation
from genome_workbench.domain.qualifiers import QualifierSet
from genome_workbench.infrastructure.blast.detector import REQUIRED_EXECUTABLES
from genome_workbench.ui.dialogs.apply_blast_hit_dialog import ApplyBlastHitDialog
from genome_workbench.ui.dialogs.batch_blast_results_dialog import BatchBlastResultsDialog
from genome_workbench.ui.dialogs.create_blast_database_dialog import CreateBlastDatabaseDialog
from genome_workbench.ui.main_window import MainWindow
from genome_workbench.ui.workers.callable_worker import CallableWorker

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"
FAKE_BLAST_DIR = FIXTURES_DIR / "fake_blast"

pytestmark = pytest.mark.ui


def _open_project_with_fasta(window: MainWindow, tmp_path: Path, monkeypatch):
    project_path = str(tmp_path / "viz" / "project.gwbproj")
    monkeypatch.setattr(
        "genome_workbench.ui.main_window.QFileDialog.getSaveFileName",
        staticmethod(lambda *a, **k: (project_path, "")),
    )
    monkeypatch.setattr(
        "genome_workbench.ui.main_window.QInputDialog.getText",
        staticmethod(lambda *a, **k: ("Viz Project", True)),
    )
    window._on_new_project()

    fasta_path = str(FIXTURES_DIR / "simple_linear.fasta")
    monkeypatch.setattr(
        "genome_workbench.ui.main_window.QFileDialog.getOpenFileName",
        staticmethod(lambda *a, **k: (fasta_path, "")),
    )
    window._on_import_fasta()
    return window.project_service.list_records()[0]


def _setup_fake_blast_and_db(window: MainWindow, tmp_path: Path, monkeypatch):
    monkeypatch.setattr(CallableWorker, "start", lambda self: self.run())

    window._blast_installation = BlastInstallation(
        directory=str(FAKE_BLAST_DIR),
        executables={name: str(FAKE_BLAST_DIR / f"{name}.bat") for name in REQUIRED_EXECUTABLES},
        versions={name: "fake 1.0" for name in REQUIRED_EXECUTABLES},
    )
    window.blast_panel.set_installation(window._blast_installation)

    db_source_fasta = tmp_path / "db_source.fasta"
    db_source_fasta.write_text(">subject1\nACGTACGTACGTACGTACGT\n")

    def _fake_create_db_exec(self):
        self._source_edit.setText(str(db_source_fasta))
        self._molecule_combo.setCurrentText("nucleotide")
        self._name_edit.setText("test_db")
        return 1

    monkeypatch.setattr(CreateBlastDatabaseDialog, "exec", _fake_create_db_exec)
    window._on_create_database_requested()
    window.blast_panel._database_list.setCurrentRow(0)
    window.blast_panel._program_combo.setCurrentText("blastn")


def test_batch_blast_runs_against_every_selected_feature(qtbot, tmp_path, monkeypatch):
    window = MainWindow(blast_work_dir=tmp_path / "blast_work")
    qtbot.addWidget(window)
    record = _open_project_with_fasta(window, tmp_path, monkeypatch)
    window._on_record_selected(record.id)
    _setup_fake_blast_and_db(window, tmp_path, monkeypatch)

    features = [
        window.annotation_service.create_simple_feature(
            record, start, start + 50, 1, "CDS", QualifierSet.from_pairs([])
        )
        for start in (101, 201, 301)
    ]
    window._refresh_features_only()

    captured = {}
    monkeypatch.setattr(
        BatchBlastResultsDialog, "exec", lambda self: captured.setdefault("dialog", self) and 1
    )

    window._on_batch_blast_requested([f.id for f in features])

    dialog = captured["dialog"]
    assert dialog._table.rowCount() == 3
    for row in range(3):
        assert dialog._table.item(row, 2).text() == "fake_subject_1"


def test_batch_blast_apply_hit_creates_annotation(qtbot, tmp_path, monkeypatch):
    window = MainWindow(blast_work_dir=tmp_path / "blast_work")
    qtbot.addWidget(window)
    record = _open_project_with_fasta(window, tmp_path, monkeypatch)
    window._on_record_selected(record.id)
    _setup_fake_blast_and_db(window, tmp_path, monkeypatch)

    features = [
        window.annotation_service.create_simple_feature(
            record, start, start + 50, 1, "CDS", QualifierSet.from_pairs([])
        )
        for start in (101, 201)
    ]
    window._refresh_features_only()
    before_count = len(window.project_service.list_features(record.id))

    def _fake_batch_dialog_exec(self):
        self._table.setCurrentCell(0, 0)
        self._on_apply_selected()
        return 1

    def _fake_apply_hit_dialog_exec(self):
        return 1

    monkeypatch.setattr(BatchBlastResultsDialog, "exec", _fake_batch_dialog_exec)
    monkeypatch.setattr(ApplyBlastHitDialog, "exec", _fake_apply_hit_dialog_exec)

    window._on_batch_blast_requested([f.id for f in features])

    after_count = len(window.project_service.list_features(record.id))
    assert after_count == before_count + 1


def test_batch_blast_requires_two_or_more_features(qtbot, tmp_path, monkeypatch):
    window = MainWindow(blast_work_dir=tmp_path / "blast_work")
    qtbot.addWidget(window)
    record = _open_project_with_fasta(window, tmp_path, monkeypatch)
    window._on_record_selected(record.id)
    _setup_fake_blast_and_db(window, tmp_path, monkeypatch)

    feature = window.annotation_service.create_simple_feature(
        record, 101, 150, 1, "CDS", QualifierSet.from_pairs([])
    )
    window._refresh_features_only()

    # only one feature id passed -- must be a no-op, not a crash
    window._on_batch_blast_requested([feature.id])

    assert window._active_worker is None


def test_batch_blast_refuses_to_start_a_second_job_while_one_is_running(
    qtbot, tmp_path, monkeypatch
):
    window = MainWindow(blast_work_dir=tmp_path / "blast_work")
    qtbot.addWidget(window)
    record = _open_project_with_fasta(window, tmp_path, monkeypatch)
    window._on_record_selected(record.id)
    _setup_fake_blast_and_db(window, tmp_path, monkeypatch)

    features = [
        window.annotation_service.create_simple_feature(
            record, start, start + 50, 1, "CDS", QualifierSet.from_pairs([])
        )
        for start in (101, 201)
    ]
    window._refresh_features_only()

    from genome_workbench.ui.workers.callable_worker import CallableWorker as RealWorker

    window._active_worker = RealWorker(lambda: None)

    monkeypatch.setattr(
        "genome_workbench.ui.main_window.QMessageBox.information",
        staticmethod(lambda *a, **k: None),
    )
    window._on_batch_blast_requested([f.id for f in features])

    # the pre-existing worker must still be the active one -- no batch started
    assert window._active_worker is not None
