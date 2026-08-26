"""AT-09: destination must be left untouched (byte-identical) if the write
callback raises, even when a valid file already exists at the destination.
"""

from pathlib import Path

import pytest

from genome_workbench.infrastructure.filesystem.atomic_write import write_atomic


def test_write_atomic_creates_new_file(tmp_path: Path):
    destination = tmp_path / "out.txt"
    write_atomic(destination, lambda p: p.write_text("hello", encoding="utf-8"))
    assert destination.read_text(encoding="utf-8") == "hello"


def test_write_atomic_leaves_existing_destination_untouched_on_failure(tmp_path: Path):
    destination = tmp_path / "out.txt"
    destination.write_text("original content", encoding="utf-8")
    original_bytes = destination.read_bytes()

    def failing_write(path: Path) -> None:
        path.write_text("partial garbage", encoding="utf-8")
        raise RuntimeError("forced failure mid-export")

    with pytest.raises(RuntimeError, match="forced failure"):
        write_atomic(destination, failing_write)

    assert destination.read_bytes() == original_bytes


def test_write_atomic_does_not_leave_temp_file_behind_on_failure(tmp_path: Path):
    destination = tmp_path / "out.txt"

    def failing_write(path: Path) -> None:
        path.write_text("partial", encoding="utf-8")
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        write_atomic(destination, failing_write)

    assert not destination.exists()
    leftovers = list(tmp_path.glob(f".{destination.name}.*"))
    assert leftovers == []


def test_write_atomic_replaces_existing_destination_on_success(tmp_path: Path):
    destination = tmp_path / "out.txt"
    destination.write_text("old", encoding="utf-8")
    write_atomic(destination, lambda p: p.write_text("new", encoding="utf-8"))
    assert destination.read_text(encoding="utf-8") == "new"


def test_write_atomic_creates_parent_directories(tmp_path: Path):
    destination = tmp_path / "nested" / "dir" / "out.txt"
    write_atomic(destination, lambda p: p.write_text("x", encoding="utf-8"))
    assert destination.read_text(encoding="utf-8") == "x"
