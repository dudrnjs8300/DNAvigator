from pathlib import Path

from genome_workbench.infrastructure.filesystem.project_lock import (
    acquire_lock,
    read_lock,
    release_lock,
)


def test_acquire_and_read_lock(tmp_path: Path):
    project_path = tmp_path / "p.gwbproj"
    assert read_lock(project_path) is None
    acquire_lock(project_path)
    info = read_lock(project_path)
    assert info is not None
    assert info.pid > 0
    assert info.hostname


def test_release_lock_removes_file(tmp_path: Path):
    project_path = tmp_path / "p.gwbproj"
    acquire_lock(project_path)
    assert read_lock(project_path) is not None
    release_lock(project_path)
    assert read_lock(project_path) is None


def test_release_lock_when_absent_is_a_noop(tmp_path: Path):
    project_path = tmp_path / "p.gwbproj"
    release_lock(project_path)  # must not raise
