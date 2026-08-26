from pathlib import Path

from genome_workbench.application.sequence_operations_service import SequenceOperationsService
from genome_workbench.domain.models import MoleculeType, SequenceRecord


def _record() -> SequenceRecord:
    return SequenceRecord(
        display_id="rec1", sequence="ATGCCCTAA", molecule_type=MoleculeType.DNA, checksum_sha256="x"
    )


def test_get_selection():
    service = SequenceOperationsService()
    assert service.get_selection(_record(), 0, 3) == "ATG"


def test_reverse_complement_selection():
    service = SequenceOperationsService()
    assert service.get_selection_reverse_complement(_record(), 0, 3) == "CAT"


def test_translation_forward():
    service = SequenceOperationsService()
    assert service.get_selection_translation(_record(), 0, 9, strand=1) == "MP"


def test_translation_reverse():
    service = SequenceOperationsService()
    record = SequenceRecord(
        sequence="TTAGGGCAT", molecule_type=MoleculeType.DNA, checksum_sha256="x"
    )
    assert service.get_selection_translation(record, 0, 9, strand=-1) == "MP"


def test_export_selection_fasta_atomic(tmp_path: Path):
    service = SequenceOperationsService()
    destination = tmp_path / "selection.fasta"
    service.export_selection_fasta(_record(), 0, 9, destination)
    content = destination.read_text()
    assert content.startswith(">rec1:1-9")
    assert "ATGCCCTAA" in content
