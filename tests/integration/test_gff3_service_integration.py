from pathlib import Path

from genome_workbench.application.export_service import ExportService
from genome_workbench.application.import_service import ImportService
from genome_workbench.application.project_service import ProjectService
from genome_workbench.domain.qualifiers import QualifierSet
from genome_workbench.infrastructure.formats.fasta_adapter import read_fasta


def test_export_gff3_embedded_then_reimport(tmp_path: Path):
    project_service = ProjectService()
    project_service.create_new(tmp_path / "p.gwbproj", "P")
    import_service = ImportService(project_service)
    export_service = ExportService(project_service)

    from genome_workbench.application.annotation_service import AnnotationService

    annotation_service = AnnotationService(project_service)

    fixtures_dir = Path(__file__).parent.parent / "fixtures"
    import_result = import_service.import_fasta(fixtures_dir / "simple_linear.fasta")
    record = import_result.records[0]
    annotation_service.create_simple_feature(
        record, 101, 900, 1, "CDS", QualifierSet.from_pairs([("gene", "exampleA")])
    )

    records = project_service.list_records()
    features = {r.id: project_service.list_features(r.id) for r in records}
    out_path = tmp_path / "export.gff3"
    export_service.export_gff3(records, features, out_path, embed_fasta=True)

    second = ProjectService()
    second.create_new(tmp_path / "p2.gwbproj", "P2")
    second_import = ImportService(second)
    reimport_result = second_import.import_gff3(out_path)
    assert len(reimport_result.records) == 1
    assert reimport_result.records[0].sequence == record.sequence
    reimported_features = reimport_result.features_by_record_id[reimport_result.records[0].id]
    assert len(reimported_features) == 1
    assert reimported_features[0].qualifiers.get_first("gene") == "exampleA"

    project_service.close()
    second.close()


def test_export_gff3_separate_fasta_then_reimport_with_pairing(tmp_path: Path):
    project_service = ProjectService()
    project_service.create_new(tmp_path / "p.gwbproj", "P")
    import_service = ImportService(project_service)
    export_service = ExportService(project_service)

    fixtures_dir = Path(__file__).parent.parent / "fixtures"
    import_result = import_service.import_fasta(fixtures_dir / "simple_linear.fasta")
    record = import_result.records[0]

    records = project_service.list_records()
    out_gff3 = tmp_path / "annotation_only.gff3"
    export_service.export_gff3(records, {record.id: []}, out_gff3, embed_fasta=False)

    text = out_gff3.read_text()
    assert "##FASTA" not in text

    fasta_result = read_fasta(fixtures_dir / "simple_linear.fasta")
    assert fasta_result.records[0].display_id == record.display_id

    second = ProjectService()
    second.create_new(tmp_path / "p2.gwbproj", "P2")
    second_import = ImportService(second)
    reimport_result = second_import.import_gff3(
        out_gff3, external_fasta_path=fixtures_dir / "simple_linear.fasta"
    )
    assert len(reimport_result.records) == 1
    assert reimport_result.records[0].sequence == record.sequence
    assert not any(issue.code == "unmatched_seqid" for issue in reimport_result.issues)

    project_service.close()
    second.close()


def test_import_gff3_unmatched_seqid_reported(tmp_path: Path):
    gff3_path = tmp_path / "unmatched.gff3"
    gff3_path.write_text(
        "##gff-version 3\ncontig_x\t.\tgene\t1\t10\t.\t+\t.\tID=g1\n", encoding="utf-8"
    )
    project_service = ProjectService()
    project_service.create_new(tmp_path / "p.gwbproj", "P")
    import_service = ImportService(project_service)
    result = import_service.import_gff3(gff3_path)
    assert any(issue.code == "unmatched_seqid" for issue in result.issues)
    project_service.close()
