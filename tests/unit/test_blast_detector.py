import stat
import sys
from pathlib import Path

from genome_workbench.infrastructure.blast import detector
from genome_workbench.infrastructure.blast.detector import find_executable


def test_find_executable_in_search_dir(tmp_path: Path):
    exe_name = "blastn.exe" if sys.platform == "win32" else "blastn"
    fake_exe = tmp_path / exe_name
    fake_exe.write_text("#!/bin/sh\necho fake\n")
    fake_exe.chmod(fake_exe.stat().st_mode | stat.S_IEXEC)

    found = find_executable("blastn", tmp_path)
    assert found == fake_exe


def test_find_executable_returns_none_when_missing(tmp_path: Path, monkeypatch):
    # Isolate from whatever BLAST+ installation (if any) actually exists on
    # the machine running the tests, so this asserts the "truly not found"
    # code path rather than incidentally depending on host state.
    monkeypatch.setattr(detector, "_common_windows_install_dirs", lambda: [])
    monkeypatch.setattr(detector.shutil, "which", lambda name: None)
    assert find_executable("blastn", tmp_path) is None
