"""Batch qualifier operations and annotation templates -- previously the
only way to edit a qualifier was one feature at a time via Inspector.
"""

from pathlib import Path

import pytest

from genome_workbench.application.annotation_service import AnnotationService
from genome_workbench.application.import_service import ImportService
from genome_workbench.application.project_service import ProjectService
from genome_workbench.domain.qualifiers import QualifierSet
from genome_workbench.infrastructure.filesystem.annotation_templates import AnnotationTemplate


def _setup(tmp_path: Path):
    project_service = ProjectService()
    project_service.create_new(tmp_path / "p.gwbproj", "P")
    import_service = ImportService(project_service)
    annotation_service = AnnotationService(project_service)
    fixtures_dir = Path(__file__).parent.parent / "fixtures"
    result = import_service.import_fasta(fixtures_dir / "simple_linear.fasta")
    return project_service, annotation_service, result.records[0]


def _three_features(annotation_service: AnnotationService, record):
    return [
        annotation_service.create_simple_feature(
            record, start, start + 50, 1, "CDS", QualifierSet.from_pairs([])
        )
        for start in (101, 201, 301)
    ]


def test_batch_set_qualifier_applies_to_all_features(tmp_path: Path):
    project_service, annotation_service, record = _setup(tmp_path)
    features = _three_features(annotation_service, record)

    updated = annotation_service.batch_update_qualifier(features, "set", "product", "putative")

    assert len(updated) == 3
    for feature in updated:
        assert feature.qualifiers.get_first("product") == "putative"
    # persisted, not just returned
    for feature in features:
        reloaded = project_service.get_repository().get_feature(feature.id)
        assert reloaded.qualifiers.get_first("product") == "putative"


def test_batch_set_replaces_existing_value(tmp_path: Path):
    project_service, annotation_service, record = _setup(tmp_path)
    features = [
        annotation_service.create_simple_feature(
            record, 101, 150, 1, "CDS", QualifierSet.from_pairs([("product", "old")])
        )
    ]

    annotation_service.batch_update_qualifier(features, "set", "product", "new")

    reloaded = project_service.get_repository().get_feature(features[0].id)
    assert reloaded.qualifiers.get("product") == ["new"]


def test_batch_add_preserves_existing_multi_value_qualifier(tmp_path: Path):
    project_service, annotation_service, record = _setup(tmp_path)
    features = [
        annotation_service.create_simple_feature(
            record, 101, 150, 1, "CDS", QualifierSet.from_pairs([("db_xref", "GO:001")])
        )
    ]

    annotation_service.batch_update_qualifier(features, "add", "db_xref", "GO:002")

    reloaded = project_service.get_repository().get_feature(features[0].id)
    assert reloaded.qualifiers.get("db_xref") == ["GO:001", "GO:002"]


def test_batch_remove_drops_qualifier(tmp_path: Path):
    project_service, annotation_service, record = _setup(tmp_path)
    features = [
        annotation_service.create_simple_feature(
            record, 101, 150, 1, "CDS", QualifierSet.from_pairs([("note", "temp")])
        )
    ]

    annotation_service.batch_update_qualifier(features, "remove", "note")

    reloaded = project_service.get_repository().get_feature(features[0].id)
    assert not reloaded.qualifiers.has("note")


def test_batch_remove_skips_features_that_never_had_the_key(tmp_path: Path):
    project_service, annotation_service, record = _setup(tmp_path)
    has_note = annotation_service.create_simple_feature(
        record, 101, 150, 1, "CDS", QualifierSet.from_pairs([("note", "x")])
    )
    no_note = annotation_service.create_simple_feature(
        record, 201, 250, 1, "CDS", QualifierSet.from_pairs([])
    )

    updated = annotation_service.batch_update_qualifier([has_note, no_note], "remove", "note")

    assert len(updated) == 1
    assert updated[0].id == has_note.id
    reloaded_no_note = project_service.get_repository().get_feature(no_note.id)
    assert reloaded_no_note.revision == no_note.revision  # untouched, not bumped


def test_batch_update_is_a_single_undo_step(tmp_path: Path):
    project_service, annotation_service, record = _setup(tmp_path)
    features = _three_features(annotation_service, record)  # 3 separate undo steps

    annotation_service.batch_update_qualifier(features, "set", "product", "putative")
    assert project_service.undo_stack.can_undo
    project_service.undo_stack.undo()  # must revert all 3 features' qualifier in one call

    for feature in features:
        reloaded = project_service.get_repository().get_feature(feature.id)
        assert not reloaded.qualifiers.has("product")
        # the undo only reverted the batch edit, not the creations beneath it
        assert reloaded is not None

    # a second undo now hits the create-commands underneath the batch,
    # proving the batch really was consumed as exactly one prior step
    project_service.undo_stack.undo()
    remaining = [f for f in features if project_service.get_repository().get_feature(f.id)]
    assert len(remaining) == 2


def test_batch_update_rejects_unknown_operation(tmp_path: Path):
    _project_service, annotation_service, record = _setup(tmp_path)
    features = _three_features(annotation_service, record)
    with pytest.raises(ValueError, match="unknown"):
        annotation_service.batch_update_qualifier(features, "explode", "product", "x")


def test_apply_template_sets_type_and_qualifiers(tmp_path: Path):
    project_service, annotation_service, record = _setup(tmp_path)
    features = _three_features(annotation_service, record)
    template = AnnotationTemplate(
        name="Bacterial CDS",
        feature_type="CDS",
        gene="",
        product="hypothetical protein",
        note="",
        transl_table="11",
        extra_qualifiers=[("EC_number", "1.1.1.1")],
    )

    annotation_service.apply_template_to_features(features, template)

    for feature in features:
        reloaded = project_service.get_repository().get_feature(feature.id)
        assert reloaded.qualifiers.get_first("product") == "hypothetical protein"
        assert reloaded.qualifiers.get_first("transl_table") == "11"
        assert reloaded.qualifiers.get_first("EC_number") == "1.1.1.1"


def test_apply_template_empty_fields_do_not_erase_existing_values(tmp_path: Path):
    project_service, annotation_service, record = _setup(tmp_path)
    features = [
        annotation_service.create_simple_feature(
            record, 101, 150, 1, "CDS", QualifierSet.from_pairs([("gene", "keepMe")])
        )
    ]
    template = AnnotationTemplate(name="No gene field", gene="", product="new product")

    annotation_service.apply_template_to_features(features, template)

    reloaded = project_service.get_repository().get_feature(features[0].id)
    assert reloaded.qualifiers.get_first("gene") == "keepMe"
    assert reloaded.qualifiers.get_first("product") == "new product"


def test_batch_operations_require_writable_project(tmp_path: Path):
    from genome_workbench.application.project_service import ProjectReadOnlyError

    path = tmp_path / "p.gwbproj"
    writer_project = ProjectService()
    writer_project.create_new(path, "P")
    import_service = ImportService(writer_project)
    annotation_service = AnnotationService(writer_project)
    fixtures_dir = Path(__file__).parent.parent / "fixtures"
    record = import_service.import_fasta(fixtures_dir / "simple_linear.fasta").records[0]
    features = _three_features(annotation_service, record)
    writer_project.close()

    reader_project = ProjectService()
    reader_project.open(path, read_only=True)
    reader_annotation_service = AnnotationService(reader_project)
    with pytest.raises(ProjectReadOnlyError):
        reader_annotation_service.batch_update_qualifier(features, "set", "product", "x")
    reader_project.close()
