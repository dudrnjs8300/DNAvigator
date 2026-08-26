"""AT-01 / Scenario A, exercised through the application service layer
(the same services the UI calls) rather than the UI itself.
"""

from pathlib import Path

from genome_workbench.application.annotation_service import AnnotationService
from genome_workbench.application.export_service import ExportService
from genome_workbench.application.import_service import ImportService
from genome_workbench.application.project_service import ProjectService
from genome_workbench.domain.qualifiers import QualifierSet
from genome_workbench.infrastructure.formats.semantic_compare import compare_semantic

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


def test_scenario_a_fasta_manual_annotation_full_round_trip(tmp_path: Path):
    project_path = tmp_path / "scenario_a" / "project.gwbproj"

    # 1-2. open project, import multi... here single-record FASTA
    project_service = ProjectService()
    project_service.create_new(project_path, "Scenario A")
    import_service = ImportService(project_service)
    annotation_service = AnnotationService(project_service)

    import_result = import_service.import_fasta(FIXTURES_DIR / "simple_linear.fasta")
    assert len(import_result.records) == 1
    record = import_result.records[0]

    # 3. contig length/GC%/topology available
    assert record.length == 1000

    # 4-6. create CDS at 101..900, + strand, gene/product qualifiers, table 11
    qualifiers = QualifierSet()
    qualifiers.add("gene", "exampleA")
    qualifiers.add("product", "example protein")
    qualifiers.add("note", "manual test")
    qualifiers.add("transl_table", "11")

    preview = annotation_service.preview_simple_feature(
        record, 101, 900, strand=1, feature_type="CDS"
    )
    assert preview.length == 800
    assert preview.translation is not None

    feature = annotation_service.create_simple_feature(
        record, 101, 900, strand=1, feature_type="CDS", qualifiers=qualifiers
    )
    assert feature.start0 == 100
    assert feature.end0 == 900

    # 7-8. undo/redo works
    assert project_service.undo_stack.can_undo
    project_service.undo_stack.undo()
    assert project_service.list_features(record.id) == []
    project_service.undo_stack.redo()
    features_after_redo = project_service.list_features(record.id)
    assert len(features_after_redo) == 1

    # close and reopen -> feature persists
    project_service.close()
    project_service.open(project_path)
    reopened_records = project_service.list_records()
    assert len(reopened_records) == 1
    reopened_features = project_service.list_features(reopened_records[0].id)
    assert len(reopened_features) == 1
    assert reopened_features[0].qualifiers.get_first("gene") == "exampleA"

    # 9. export to GenBank, reimport into a fresh project, compare semantically
    export_service = ExportService(project_service)
    gbk_path = tmp_path / "scenario_a" / "export.gbk"
    export_result = export_service.export_genbank(
        reopened_records,
        {reopened_records[0].id: reopened_features},
        gbk_path,
    )
    assert gbk_path.exists()

    second_project_path = tmp_path / "scenario_a" / "reimport.gwbproj"
    second_project = ProjectService()
    second_project.create_new(second_project_path, "Reimport check")
    second_import = ImportService(second_project)
    reimport_result = second_import.import_genbank(gbk_path)
    assert len(reimport_result.records) == 1

    diffs = compare_semantic(
        reopened_records,
        {reopened_records[0].id: reopened_features},
        reimport_result.records,
        reimport_result.features_by_record_id,
    )
    errors = [d for d in diffs if d.severity == "error"]
    assert errors == [], errors

    reimported_feature = reimport_result.features_by_record_id[reimport_result.records[0].id][0]
    assert reimported_feature.qualifiers.get_first("gene") == "exampleA"
    assert reimported_feature.qualifiers.get_first("product") == "example protein"
    assert reimported_feature.qualifiers.get_first("note") == "manual test"

    second_project.close()
    project_service.close()
    _ = export_result
