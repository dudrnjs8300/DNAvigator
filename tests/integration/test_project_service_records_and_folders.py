"""Record deletion and folder organization (ProjectService layer).

Both were missing from the UI entirely until this session: there was no way
for a user to remove an imported record or group records into folders in the
Project Explorer.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from genome_workbench.application.project_service import NoOpenProjectError, ProjectService
from genome_workbench.domain.models import MoleculeType, SequenceRecord, Topology


@pytest.fixture
def service(tmp_path: Path) -> ProjectService:
    svc = ProjectService()
    svc.create_new(tmp_path / "p.gwbproj", "P")
    return svc


def _add_record(service: ProjectService, display_id: str) -> SequenceRecord:
    repo = service.get_repository()
    record = SequenceRecord(
        display_id=display_id,
        sequence="ACGT" * 50,
        checksum_sha256="x",
        molecule_type=MoleculeType.DNA,
    )
    repo.save_record(record)
    return record


def test_delete_record_removes_it_and_its_features(service: ProjectService):
    from genome_workbench.domain.locations import LocationPart
    from genome_workbench.domain.models import Feature

    record = _add_record(service, "contig1")
    feature = Feature(
        record_id=record.id, type="CDS", parts=[LocationPart(start0=0, end0=10, order_index=0)]
    )
    service.get_repository().save_feature(feature)

    service.delete_record(record.id)

    assert service.get_record(record.id) is None
    assert service.list_features(record.id) == []


def test_delete_record_unknown_id_raises(service: ProjectService):
    with pytest.raises(NoOpenProjectError):
        service.delete_record("does-not-exist")


def test_create_folder_and_list_folders(service: ProjectService):
    folder = service.create_folder("Isolates")
    assert folder.parent_folder_id is None
    assert [f.id for f in service.list_folders()] == [folder.id]


def test_nested_folder_creation(service: ProjectService):
    parent = service.create_folder("Isolates")
    child = service.create_folder("2026 batch", parent_folder_id=parent.id)
    assert child.parent_folder_id == parent.id


def test_rename_folder(service: ProjectService):
    folder = service.create_folder("Old name")
    renamed = service.rename_folder(folder.id, "New name")
    assert renamed.name == "New name"
    assert service.list_folders()[0].name == "New name"


def test_move_record_to_folder_and_back_to_root(service: ProjectService):
    folder = service.create_folder("Isolates")
    record = _add_record(service, "contig1")

    moved = service.move_record_to_folder(record.id, folder.id)
    assert moved.folder_id == folder.id

    back = service.move_record_to_folder(record.id, None)
    assert back.folder_id is None


def test_delete_folder_moves_contents_up_instead_of_deleting_them(service: ProjectService):
    grandparent = service.create_folder("Project A")
    parent = service.create_folder("Isolates", parent_folder_id=grandparent.id)
    record = _add_record(service, "contig1")
    service.move_record_to_folder(record.id, parent.id)
    child_folder = service.create_folder("2026 batch", parent_folder_id=parent.id)

    service.delete_folder(parent.id)

    # the deleted folder itself is gone
    assert service.get_repository().get_folder(parent.id) is None
    # but its contents moved up to its own parent, not vanished
    moved_record = service.get_record(record.id)
    assert moved_record is not None
    assert moved_record.folder_id == grandparent.id
    moved_child_folder = next(f for f in service.list_folders() if f.id == child_folder.id)
    assert moved_child_folder.parent_folder_id == grandparent.id


def test_delete_root_folder_moves_contents_to_project_root(service: ProjectService):
    folder = service.create_folder("Isolates")
    record = _add_record(service, "contig1")
    service.move_record_to_folder(record.id, folder.id)

    service.delete_folder(folder.id)

    assert service.get_record(record.id).folder_id is None


def test_move_folder_into_itself_rejected(service: ProjectService):
    folder = service.create_folder("Isolates")
    with pytest.raises(ValueError, match="itself"):
        service.move_folder(folder.id, folder.id)


def test_move_folder_into_its_own_descendant_rejected(service: ProjectService):
    parent = service.create_folder("Isolates")
    child = service.create_folder("2026 batch", parent_folder_id=parent.id)
    with pytest.raises(ValueError, match="subfolder"):
        service.move_folder(parent.id, child.id)


def test_move_folder_to_new_valid_parent(service: ProjectService):
    a = service.create_folder("A")
    b = service.create_folder("B")
    moved = service.move_folder(b.id, a.id)
    assert moved.parent_folder_id == a.id


def test_mutations_require_writable_project(tmp_path: Path):
    from genome_workbench.application.project_service import ProjectReadOnlyError

    path = tmp_path / "p.gwbproj"
    writer = ProjectService()
    writer.create_new(path, "P")
    folder = writer.create_folder("Isolates")
    writer.close()

    reader = ProjectService()
    reader.open(path, read_only=True)
    with pytest.raises(ProjectReadOnlyError):
        reader.create_folder("Should fail")
    with pytest.raises(ProjectReadOnlyError):
        reader.delete_folder(folder.id)
    with pytest.raises(ProjectReadOnlyError):
        reader.move_record_to_folder("whatever", folder.id)
    reader.close()


def test_set_record_topology_is_undoable(service: ProjectService):
    """Record topology (linear/circular) previously bypassed the undo stack
    entirely (KNOWN_LIMITATIONS.md gap) -- a mis-click had no way back short
    of manually flipping it again."""
    record = _add_record(service, "r1")
    record.topology = Topology.LINEAR
    service.get_repository().save_record(record)

    updated = service.set_record_topology(record.id, Topology.CIRCULAR)
    assert updated.topology == Topology.CIRCULAR
    assert service.get_record(record.id).topology == Topology.CIRCULAR
    assert service.undo_stack.can_undo

    assert service.undo_stack.undo() is True
    assert service.get_record(record.id).topology == Topology.LINEAR

    assert service.undo_stack.redo() is True
    assert service.get_record(record.id).topology == Topology.CIRCULAR
