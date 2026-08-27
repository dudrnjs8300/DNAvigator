from pathlib import Path

from genome_workbench.application.sequence_operations_service import SequenceOperationsService
from genome_workbench.domain.locations import LocationPart
from genome_workbench.domain.models import Feature, MoleculeType, SequenceRecord
from genome_workbench.domain.qualifiers import QualifierSet


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


def test_extract_as_new_record_does_not_mutate_original():
    service = SequenceOperationsService()
    original = _record()
    new_record = service.extract_as_new_record(original, 0, 3)
    assert new_record.sequence == "ATG"
    assert new_record.id != original.id
    assert original.sequence == "ATGCCCTAA"  # unchanged


def test_extract_as_new_record_reverse_strand():
    service = SequenceOperationsService()
    new_record = service.extract_as_new_record(_record(), 0, 3, strand=-1)
    assert new_record.sequence == "CAT"
    assert "(-)" in new_record.description


def test_reverse_complement_as_new_record_does_not_mutate_original():
    service = SequenceOperationsService()
    original = _record()
    new_record = service.reverse_complement_as_new_record(original)
    assert new_record.sequence == "TTAGGGCAT"
    assert original.sequence == "ATGCCCTAA"  # unchanged
    assert new_record.id != original.id


def _feature(start0: int, end0: int, strand: int = 1, gene: str = "g1") -> Feature:
    return Feature(
        record_id="orig-record",
        type="CDS",
        strand=strand,
        parts=[LocationPart(start0=start0, end0=end0, order_index=0)],
        qualifiers=QualifierSet.from_pairs([("gene", gene)]),
    )


def test_extract_with_features_rebases_a_fully_contained_feature():
    service = SequenceOperationsService()
    record = _record()  # "ATGCCCTAA", 9 bp
    feature = _feature(2, 5)  # "GCC", inside the 0..9 extraction

    new_record, new_features = service.extract_as_new_record_with_features(record, [feature], 0, 9)

    assert new_record.sequence == "ATGCCCTAA"
    assert len(new_features) == 1
    assert (new_features[0].start0, new_features[0].end0) == (2, 5)
    assert new_features[0].qualifiers.get_first("gene") == "g1"


def test_extract_with_features_rebases_relative_to_extraction_start():
    service = SequenceOperationsService()
    record = _record()
    feature = _feature(4, 7)  # "CCT", inside a 3..9 extraction

    new_record, new_features = service.extract_as_new_record_with_features(record, [feature], 3, 9)

    assert new_record.sequence == "CCCTAA"
    assert (new_features[0].start0, new_features[0].end0) == (1, 4)


def test_extract_with_features_drops_partially_overlapping_feature():
    service = SequenceOperationsService()
    record = _record()
    # feature spans 1..5, extraction range is 3..9 -- only partially inside
    feature = _feature(1, 5)

    _new_record, new_features = service.extract_as_new_record_with_features(record, [feature], 3, 9)

    assert new_features == []


def test_extract_with_features_drops_feature_entirely_outside_range():
    service = SequenceOperationsService()
    record = _record()
    feature = _feature(0, 2)

    _new_record, new_features = service.extract_as_new_record_with_features(record, [feature], 5, 9)

    assert new_features == []


def test_extract_with_features_reverse_strand_mirrors_coordinates_and_strand():
    service = SequenceOperationsService()
    record = _record()  # "ATGCCCTAA", 9bp
    feature = _feature(2, 5, strand=1)  # "GCC" at 2..5

    new_record, new_features = service.extract_as_new_record_with_features(
        record, [feature], 0, 9, strand=-1
    )

    assert new_record.sequence == "TTAGGGCAT"  # reverse complement of the whole 9bp
    # region_length=9; mirrored: start=9-5=4, end=9-2=7
    assert (new_features[0].start0, new_features[0].end0) == (4, 7)
    assert new_features[0].strand == -1


def test_extract_with_features_clears_cross_references_and_record_id():
    service = SequenceOperationsService()
    record = _record()
    feature = _feature(0, 9)
    feature.parent_ids = ["parent-1"]
    feature.child_ids = ["child-1"]
    feature.provenance_id = "prov-1"

    _new_record, new_features = service.extract_as_new_record_with_features(record, [feature], 0, 9)

    copied = new_features[0]
    assert copied.record_id == ""
    assert copied.parent_ids == []
    assert copied.child_ids == []
    assert copied.provenance_id is None
    assert copied.id != feature.id


def test_extract_with_features_qualifiers_are_not_aliased():
    service = SequenceOperationsService()
    record = _record()
    feature = _feature(0, 9)

    _new_record, new_features = service.extract_as_new_record_with_features(record, [feature], 0, 9)

    new_features[0].qualifiers.add("note", "added after extraction")
    assert feature.qualifiers.get_first("note") is None
