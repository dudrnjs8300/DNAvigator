from pathlib import Path

from genome_workbench.application.annotation_service import AnnotationService
from genome_workbench.application.import_service import ImportService
from genome_workbench.application.project_service import ProjectService
from genome_workbench.domain.locations import LocationOperator
from genome_workbench.domain.qualifiers import QualifierSet
from genome_workbench.domain.sequence_ops import reverse_complement


def _setup(tmp_path: Path):
    project_service = ProjectService()
    project_service.create_new(tmp_path / "p.gwbproj", "P")
    import_service = ImportService(project_service)
    annotation_service = AnnotationService(project_service)
    fixtures_dir = Path(__file__).parent.parent / "fixtures"
    result = import_service.import_fasta(fixtures_dir / "simple_linear.fasta")
    return project_service, annotation_service, result.records[0]


def test_create_compound_feature_forward_strand_concatenates_in_ascending_order(tmp_path: Path):
    project_service, annotation_service, record = _setup(tmp_path)
    feature = annotation_service.create_compound_feature(
        record,
        [(101, 150), (300, 350)],
        strand=1,
        feature_type="CDS",
        qualifiers=QualifierSet.from_pairs([("gene", "joinTest")]),
    )
    assert feature.location_operator == LocationOperator.JOIN
    assert [(p.start0, p.end0) for p in feature.parts] == [(100, 150), (299, 350)]
    project_service.close()


def test_create_compound_feature_reverse_strand_uses_descending_biological_order(tmp_path: Path):
    project_service, annotation_service, record = _setup(tmp_path)
    # user enters segments in any order; ascending genomic order is derived internally
    feature = annotation_service.create_compound_feature(
        record,
        [(300, 350), (101, 150)],
        strand=-1,
        feature_type="CDS",
        qualifiers=QualifierSet.from_pairs([("gene", "joinTestRev")]),
    )
    # minus strand -> order_index must be descending genomic order (D-002)
    assert [(p.start0, p.end0) for p in feature.parts] == [(299, 350), (100, 150)]
    project_service.close()


def test_preview_compound_feature_matches_created_feature_extraction(tmp_path: Path):
    from genome_workbench.domain.locations import extract_sequence

    project_service, annotation_service, record = _setup(tmp_path)
    preview = annotation_service.preview_compound_feature(
        record, [(101, 150), (300, 350)], strand=-1, feature_type="misc_feature"
    )
    feature = annotation_service.create_compound_feature(
        record,
        [(101, 150), (300, 350)],
        strand=-1,
        feature_type="misc_feature",
        qualifiers=QualifierSet(),
    )
    nt = extract_sequence(record.sequence, feature.parts, feature.strand, record.length)
    assert preview.nucleotide == nt
    assert preview.length == 101  # (150-100) + (350-299)
    project_service.close()


def test_preview_compound_reverse_matches_manual_rc_of_each_segment(tmp_path: Path):
    project_service, annotation_service, record = _setup(tmp_path)
    preview = annotation_service.preview_compound_feature(
        record, [(101, 150), (300, 350)], strand=-1, feature_type="misc_feature"
    )
    seg1 = record.sequence[100:150]
    seg2 = record.sequence[299:350]
    # strand -1: individually RC each part, concatenate in descending-order (D-002)
    expected = reverse_complement(seg2) + reverse_complement(seg1)
    assert preview.nucleotide == expected
    project_service.close()
