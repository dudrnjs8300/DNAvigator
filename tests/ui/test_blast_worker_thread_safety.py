"""Regression test for a real crash a user hit: 'Database Creation Failed --
SQLite objects created in a thread can only be used in that same thread.'

BlastService.create_database/run_search used to call
project_service.log_audit(...) directly from inside the method body, but
those methods run on a background QThread (see ui/workers/callable_worker.py)
while the project's SQLite connection was opened on the main/UI thread.
sqlite3 connections are single-thread-only by default, so this crashed every
database creation or search whenever a project was open.

The rest of the BLAST test suite monkeypatches CallableWorker.start to run
synchronously (`lambda self: self.run()`) for speed/determinism -- which
also happens to run the worker body on the *same* thread as the test, so it
never exercised the real cross-thread path and never caught this. These
tests deliberately do NOT apply that monkeypatch.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from genome_workbench.domain.blast_models import BlastInstallation
from genome_workbench.infrastructure.blast.detector import REQUIRED_EXECUTABLES
from genome_workbench.ui.dialogs.create_blast_database_dialog import CreateBlastDatabaseDialog
from genome_workbench.ui.main_window import MainWindow

pytestmark = pytest.mark.ui

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"
FAKE_BLAST_DIR = FIXTURES_DIR / "fake_blast"


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


def _install_fake_blast(window: MainWindow) -> None:
    window._blast_installation = BlastInstallation(
        directory=str(FAKE_BLAST_DIR),
        executables={name: str(FAKE_BLAST_DIR / f"{name}.bat") for name in REQUIRED_EXECUTABLES},
        versions={name: "fake 1.0" for name in REQUIRED_EXECUTABLES},
    )
    window.blast_panel.set_installation(window._blast_installation)


def test_create_database_on_a_real_thread_with_project_open_does_not_crash(
    qtbot, tmp_path, monkeypatch
):
    window = MainWindow(blast_work_dir=tmp_path / "blast_work")
    qtbot.addWidget(window)
    _open_project_with_fasta(window, tmp_path, monkeypatch)
    assert window.project_service.is_open
    _install_fake_blast(window)

    db_source_fasta = tmp_path / "db_source.fasta"
    db_source_fasta.write_text(">subject1\nACGTACGTACGTACGTACGT\n")

    def _fake_create_db_exec(self):
        self._source_edit.setText(str(db_source_fasta))
        self._molecule_combo.setCurrentText("nucleotide")
        self._name_edit.setText("test_db")
        return 1

    monkeypatch.setattr(CreateBlastDatabaseDialog, "exec", _fake_create_db_exec)

    failures: list[str] = []
    window._on_create_database_requested()
    worker = window._active_worker
    assert worker is not None  # a real QThread is actually running
    worker.failed.connect(failures.append)

    qtbot.waitUntil(lambda: window._active_worker is None, timeout=10000)

    assert failures == []  # must not have hit the cross-thread SQLite crash
    assert len(window.blast_service.list_databases()) == 1
    events = window.project_service.get_repository().list_audit_events()
    assert any("Created BLAST database" in e.summary for e in events)


def test_run_search_on_a_real_thread_with_project_open_does_not_crash(qtbot, tmp_path, monkeypatch):
    window = MainWindow(blast_work_dir=tmp_path / "blast_work")
    qtbot.addWidget(window)
    record = _open_project_with_fasta(window, tmp_path, monkeypatch)
    window._on_record_selected(record.id)
    assert window.project_service.is_open
    _install_fake_blast(window)

    db_source_fasta = tmp_path / "db_source.fasta"
    db_source_fasta.write_text(">subject1\nACGTACGTACGTACGTACGT\n")

    def _fake_create_db_exec(self):
        self._source_edit.setText(str(db_source_fasta))
        self._molecule_combo.setCurrentText("nucleotide")
        self._name_edit.setText("test_db")
        return 1

    monkeypatch.setattr(CreateBlastDatabaseDialog, "exec", _fake_create_db_exec)
    window._on_create_database_requested()
    qtbot.waitUntil(lambda: window._active_worker is None, timeout=10000)

    window._start_blast_from_selection(record, 100, 400)
    window.blast_panel._database_list.setCurrentRow(0)
    window.blast_panel._program_combo.setCurrentText("blastn")

    failures: list[str] = []
    window._on_run_blast_requested()
    worker = window._active_worker
    assert worker is not None
    worker.failed.connect(failures.append)

    qtbot.waitUntil(lambda: window._active_worker is None, timeout=10000)

    assert failures == []
    assert window._last_blast_result is not None
    events = window.project_service.get_repository().list_audit_events()
    assert any("blastn vs" in e.summary for e in events)
