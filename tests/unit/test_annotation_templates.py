from pathlib import Path

from genome_workbench.infrastructure.filesystem.annotation_templates import (
    AnnotationTemplate,
    delete_template,
    load_templates,
    upsert_template,
)


def test_load_templates_empty_when_no_file(tmp_path: Path):
    assert load_templates(tmp_path) == []


def test_upsert_then_load_round_trip(tmp_path: Path):
    template = AnnotationTemplate(
        name="Bacterial CDS",
        feature_type="CDS",
        gene="",
        product="hypothetical protein",
        note="",
        transl_table="11",
        extra_qualifiers=[("EC_number", "1.1.1.1")],
    )
    upsert_template(template, tmp_path)

    loaded = load_templates(tmp_path)
    assert len(loaded) == 1
    assert loaded[0].name == "Bacterial CDS"
    assert loaded[0].product == "hypothetical protein"
    assert loaded[0].extra_qualifiers == [("EC_number", "1.1.1.1")]


def test_upsert_replaces_existing_template_with_same_name(tmp_path: Path):
    upsert_template(AnnotationTemplate(name="X", product="old"), tmp_path)
    upsert_template(AnnotationTemplate(name="X", product="new"), tmp_path)

    loaded = load_templates(tmp_path)
    assert len(loaded) == 1
    assert loaded[0].product == "new"


def test_multiple_templates_sorted_by_name(tmp_path: Path):
    upsert_template(AnnotationTemplate(name="Zebra"), tmp_path)
    upsert_template(AnnotationTemplate(name="Alpha"), tmp_path)

    loaded = load_templates(tmp_path)
    assert [t.name for t in loaded] == ["Alpha", "Zebra"]


def test_delete_template_removes_only_the_named_one(tmp_path: Path):
    upsert_template(AnnotationTemplate(name="Keep"), tmp_path)
    upsert_template(AnnotationTemplate(name="Remove"), tmp_path)

    delete_template("Remove", tmp_path)

    loaded = load_templates(tmp_path)
    assert [t.name for t in loaded] == ["Keep"]


def test_upsert_creates_missing_parent_directory(tmp_path: Path):
    not_yet_created = tmp_path / "does" / "not" / "exist"
    upsert_template(AnnotationTemplate(name="X"), not_yet_created)
    assert load_templates(not_yet_created)[0].name == "X"


def test_corrupt_json_file_treated_as_empty(tmp_path: Path):
    from genome_workbench.infrastructure.filesystem.annotation_templates import templates_path

    templates_path(tmp_path).write_text("not valid json{{{", encoding="utf-8")
    assert load_templates(tmp_path) == []
