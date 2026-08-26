"""Batch qualifier editing and annotation templates through the actual UI:
Feature Table multi-select -> batch dialog -> MainWindow -> AnnotationService,
and AddFeatureDialog's template combo for creating features from a preset.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QMessageBox, QTableWidgetSelectionRange

from genome_workbench.domain.qualifiers import QualifierSet
from genome_workbench.infrastructure.filesystem.annotation_templates import (
    AnnotationTemplate,
    load_templates,
    upsert_template,
)
from genome_workbench.ui.dialogs.add_feature_dialog import AddFeatureDialog
from genome_workbench.ui.dialogs.batch_qualifier_dialog import BatchQualifierDialog
from genome_workbench.ui.main_window import MainWindow

pytestmark = pytest.mark.ui

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


def _open_project_with_fasta(window: MainWindow, tmp_path: Path, monkeypatch):
    project_path = str(tmp_path / "viz" / "project.gwbproj")
    monkeypatch.setattr(
        "genome_workbench.ui.main_window.QFileDialog.getSaveFileName",
        staticmethod(lambda *a, **k: (project_path, "")),
    )
    monkeypatch.setattr(
        "genome_workbench.ui.main_window.QInputDialog.getText",
        staticmethod(lambda *a, **k: ("Viz Project", True)),
    )
    window._on_new_project()

    fasta_path = str(FIXTURES_DIR / "simple_linear.fasta")
    monkeypatch.setattr(
        "genome_workbench.ui.main_window.QFileDialog.getOpenFileName",
        staticmethod(lambda *a, **k: (fasta_path, "")),
    )
    window._on_import_fasta()
    return window.project_service.list_records()[0]


def _three_features(window: MainWindow, record):
    return [
        window.annotation_service.create_simple_feature(
            record, start, start + 50, 1, "CDS", QualifierSet.from_pairs([])
        )
        for start in (101, 201, 301)
    ]


# -- FeatureTableView: multi-select --------------------------------------


def test_feature_table_multi_select_reports_all_selected_ids(qtbot, tmp_path, monkeypatch):
    window = MainWindow(blast_work_dir=tmp_path / "blast_work")
    qtbot.addWidget(window)
    record = _open_project_with_fasta(window, tmp_path, monkeypatch)
    features = _three_features(window, record)
    window._refresh_features_only()

    window.feature_table.setRangeSelected(
        QTableWidgetSelectionRange(0, 0, window.feature_table.rowCount() - 1, 0), True
    )

    selected_ids = set(window.feature_table.selected_feature_ids())
    assert selected_ids == {f.id for f in features}


# -- Batch qualifier edit through MainWindow -------------------------------


def test_batch_edit_qualifiers_sets_value_on_all_selected(qtbot, tmp_path, monkeypatch):
    window = MainWindow(blast_work_dir=tmp_path / "blast_work")
    qtbot.addWidget(window)
    record = _open_project_with_fasta(window, tmp_path, monkeypatch)
    features = _three_features(window, record)
    window._on_record_selected(record.id)

    def _fake_exec(self):
        self._operation_combo.setCurrentIndex(0)  # Set (replace)
        self._key_combo.setCurrentText("product")
        self._value_edit.setText("putative")
        return 1

    monkeypatch.setattr(BatchQualifierDialog, "exec", _fake_exec)

    window._on_batch_edit_qualifiers_requested([f.id for f in features])

    for feature in features:
        reloaded = window.project_service.get_repository().get_feature(feature.id)
        assert reloaded.qualifiers.get_first("product") == "putative"


def test_batch_edit_cancelled_dialog_changes_nothing(qtbot, tmp_path, monkeypatch):
    window = MainWindow(blast_work_dir=tmp_path / "blast_work")
    qtbot.addWidget(window)
    record = _open_project_with_fasta(window, tmp_path, monkeypatch)
    features = _three_features(window, record)
    window._on_record_selected(record.id)

    monkeypatch.setattr(BatchQualifierDialog, "exec", lambda self: 0)  # Cancel

    window._on_batch_edit_qualifiers_requested([f.id for f in features])

    for feature in features:
        reloaded = window.project_service.get_repository().get_feature(feature.id)
        assert not reloaded.qualifiers.has("product")


# -- Apply template to selected features through MainWindow -----------------


def test_apply_template_to_selected_features(qtbot, tmp_path, monkeypatch):
    templates_dir = tmp_path / "templates"
    window = MainWindow(blast_work_dir=tmp_path / "blast_work", templates_dir=templates_dir)
    qtbot.addWidget(window)
    record = _open_project_with_fasta(window, tmp_path, monkeypatch)
    features = _three_features(window, record)
    window._on_record_selected(record.id)

    upsert_template(
        AnnotationTemplate(name="Bacterial CDS", product="hypothetical protein"), templates_dir
    )
    monkeypatch.setattr(
        "genome_workbench.ui.main_window.QInputDialog.getItem",
        staticmethod(lambda *a, **k: ("Bacterial CDS", True)),
    )

    window._on_apply_template_requested([f.id for f in features])

    for feature in features:
        reloaded = window.project_service.get_repository().get_feature(feature.id)
        assert reloaded.qualifiers.get_first("product") == "hypothetical protein"


def test_apply_template_with_no_saved_templates_shows_message_and_does_nothing(
    qtbot, tmp_path, monkeypatch
):
    templates_dir = tmp_path / "empty_templates"
    window = MainWindow(blast_work_dir=tmp_path / "blast_work", templates_dir=templates_dir)
    qtbot.addWidget(window)
    record = _open_project_with_fasta(window, tmp_path, monkeypatch)
    features = _three_features(window, record)
    window._on_record_selected(record.id)

    monkeypatch.setattr(
        "genome_workbench.ui.main_window.QMessageBox.information",
        staticmethod(lambda *a, **k: None),
    )

    window._on_apply_template_requested([f.id for f in features])

    for feature in features:
        reloaded = window.project_service.get_repository().get_feature(feature.id)
        assert not reloaded.qualifiers.has("product")


# -- AddFeatureDialog: template combo (create with a saved preset) ----------


def test_add_feature_dialog_saves_and_reapplies_template(qtbot, tmp_path, monkeypatch):
    templates_dir = tmp_path / "templates"
    window = MainWindow(blast_work_dir=tmp_path / "blast_work", templates_dir=templates_dir)
    qtbot.addWidget(window)
    record = _open_project_with_fasta(window, tmp_path, monkeypatch)

    dialog = AddFeatureDialog(
        record, window.annotation_service, window, templates_dir=templates_dir
    )
    qtbot.addWidget(dialog)
    dialog._type_combo.setCurrentText("CDS")
    dialog._product_edit.setText("hypothetical protein")
    dialog._transl_table_edit.setText("11")

    monkeypatch.setattr(
        "genome_workbench.ui.dialogs.add_feature_dialog.QInputDialog.getText",
        staticmethod(lambda *a, **k: ("My Template", True)),
    )
    dialog._on_save_template()

    saved = load_templates(templates_dir)
    assert len(saved) == 1
    assert saved[0].name == "My Template"
    assert saved[0].product == "hypothetical protein"

    # a fresh dialog picks up the saved template and applying it fills fields
    dialog2 = AddFeatureDialog(
        record, window.annotation_service, window, templates_dir=templates_dir
    )
    qtbot.addWidget(dialog2)
    dialog2._product_edit.clear()
    index = dialog2._template_combo.findText("My Template")
    assert index >= 0
    dialog2._template_combo.setCurrentIndex(index)

    assert dialog2._product_edit.text() == "hypothetical protein"
    assert dialog2._transl_table_edit.text() == "11"


def test_add_feature_dialog_created_feature_uses_template_qualifiers(qtbot, tmp_path, monkeypatch):
    templates_dir = tmp_path / "templates"
    window = MainWindow(blast_work_dir=tmp_path / "blast_work", templates_dir=templates_dir)
    qtbot.addWidget(window)
    record = _open_project_with_fasta(window, tmp_path, monkeypatch)

    upsert_template(
        AnnotationTemplate(name="Bacterial CDS", product="hypothetical protein"), templates_dir
    )

    dialog = AddFeatureDialog(
        record, window.annotation_service, window, templates_dir=templates_dir
    )
    qtbot.addWidget(dialog)
    index = dialog._template_combo.findText("Bacterial CDS")
    dialog._template_combo.setCurrentIndex(index)
    dialog._start_spin.setValue(101)
    dialog._end_spin.setValue(200)

    dialog._on_accept()

    assert dialog.created_feature is not None
    assert dialog.created_feature.qualifiers.get_first("product") == "hypothetical protein"


def test_add_feature_dialog_delete_template(qtbot, tmp_path, monkeypatch):
    templates_dir = tmp_path / "templates"
    window = MainWindow(blast_work_dir=tmp_path / "blast_work", templates_dir=templates_dir)
    qtbot.addWidget(window)
    record = _open_project_with_fasta(window, tmp_path, monkeypatch)

    upsert_template(AnnotationTemplate(name="To Delete"), templates_dir)

    dialog = AddFeatureDialog(
        record, window.annotation_service, window, templates_dir=templates_dir
    )
    qtbot.addWidget(dialog)
    index = dialog._template_combo.findText("To Delete")
    dialog._template_combo.setCurrentIndex(index)

    monkeypatch.setattr(
        "genome_workbench.ui.dialogs.add_feature_dialog.QMessageBox.question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes),
    )
    dialog._on_delete_template()

    assert load_templates(templates_dir) == []
