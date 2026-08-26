from pathlib import Path

import pytest

from genome_workbench.application.project_service import (
    ProjectReadOnlyError,
    ProjectService,
)
from genome_workbench.infrastructure.filesystem.project_lock import (
    ProjectLockedError,
    read_lock,
    release_lock,
)


def test_create_new_acquires_lock_and_close_releases_it(tmp_path: Path):
    path = tmp_path / "p.gwbproj"
    service = ProjectService()
    service.create_new(path, "P")
    assert read_lock(path) is not None
    service.close()
    assert read_lock(path) is None


def test_second_open_without_force_raises_locked_error(tmp_path: Path):
    path = tmp_path / "p.gwbproj"
    first = ProjectService()
    first.create_new(path, "P")

    second = ProjectService()
    with pytest.raises(ProjectLockedError):
        second.open(path)

    first.close()


def test_open_read_only_does_not_require_lock_and_blocks_mutation(tmp_path: Path):
    from genome_workbench.application.annotation_service import AnnotationService
    from genome_workbench.application.import_service import ImportService
    from genome_workbench.domain.qualifiers import QualifierSet

    path = tmp_path / "p.gwbproj"
    first = ProjectService()
    first.create_new(path, "P")
    fixtures_dir = Path(__file__).parent.parent / "fixtures"
    ImportService(first).import_fasta(fixtures_dir / "simple_linear.fasta")
    record = first.list_records()[0]

    second = ProjectService()
    second.open(path, read_only=True)
    assert second.is_read_only

    annotation_service = AnnotationService(second)
    with pytest.raises(ProjectReadOnlyError):
        annotation_service.create_simple_feature(record, 1, 10, 1, "misc_feature", QualifierSet())

    second.close()
    first.close()


def test_force_open_bypasses_lock_and_is_writable(tmp_path: Path):
    path = tmp_path / "p.gwbproj"
    first = ProjectService()
    first.create_new(path, "P")

    second = ProjectService()
    second.open(path, force=True)
    assert not second.is_read_only

    first.close()
    second.close()


def test_stale_lock_from_uncleanly_closed_session_is_detected(tmp_path: Path):
    path = tmp_path / "p.gwbproj"
    service = ProjectService()
    service.create_new(path, "P")
    # simulate a crash: repo connection is closed but the lock file is never released
    service._repo.close()  # noqa: SLF001
    service._repo = None  # noqa: SLF001

    reopener = ProjectService()
    with pytest.raises(ProjectLockedError):
        reopener.open(path)
    release_lock(path)
