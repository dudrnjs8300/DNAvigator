"""Export the genome/circular map as a PNG or SVG figure -- previously the
only way to get a picture of the map out of the app was a screen capture,
which isn't sharp enough to use directly in a paper (user-reported gap)."""

from __future__ import annotations

from pathlib import Path

import pytest

from genome_workbench.domain.locations import LocationPart
from genome_workbench.domain.models import Feature, MoleculeType, SequenceRecord, Topology
from genome_workbench.ui.rendering.image_export import ImageExportError, export_widget_as_image
from genome_workbench.ui.views.circular_genome_canvas import CircularGenomeCanvas
from genome_workbench.ui.views.genome_canvas import GenomeCanvas

pytestmark = pytest.mark.ui


def _record() -> SequenceRecord:
    return SequenceRecord(
        display_id="export_test",
        sequence="ACGT" * 250,
        checksum_sha256="x",
        molecule_type=MoleculeType.DNA,
        topology=Topology.CIRCULAR,
    )


def _feature() -> Feature:
    return Feature(type="CDS", strand=1, parts=[LocationPart(start0=0, end0=100, order_index=0)])


def test_export_png_writes_a_scaled_up_file(qtbot, tmp_path: Path):
    canvas = GenomeCanvas()
    qtbot.addWidget(canvas)
    canvas.resize(400, 200)
    canvas.set_record(_record(), [_feature()])
    canvas.set_viewport(0, 1000)

    out = tmp_path / "map.png"
    export_widget_as_image(canvas, out, png_scale=3)

    assert out.exists()
    from PySide6.QtGui import QImage

    image = QImage(str(out))
    assert image.width() == 400 * 3
    assert image.height() == 200 * 3


def test_export_png_default_scale_matches_widget_size(qtbot, tmp_path: Path):
    canvas = GenomeCanvas()
    qtbot.addWidget(canvas)
    canvas.resize(300, 250)  # above GenomeCanvas's minimum height
    canvas.set_record(_record(), [])
    canvas.set_viewport(0, 1000)

    out = tmp_path / "map.png"
    export_widget_as_image(canvas, out)

    from PySide6.QtGui import QImage

    image = QImage(str(out))
    assert (image.width(), image.height()) == (canvas.width(), canvas.height())


def test_export_svg_writes_a_vector_file(qtbot, tmp_path: Path):
    canvas = CircularGenomeCanvas()
    qtbot.addWidget(canvas)
    canvas.resize(300, 300)
    canvas.set_record(_record(), [_feature()])

    out = tmp_path / "map.svg"
    export_widget_as_image(canvas, out)

    assert out.exists()
    content = out.read_text(encoding="utf-8")
    assert "<svg" in content


def test_export_with_zero_size_widget_raises(qtbot, tmp_path: Path):
    canvas = GenomeCanvas()
    qtbot.addWidget(canvas)
    canvas.resize(0, 0)

    with pytest.raises(ImageExportError):
        export_widget_as_image(canvas, tmp_path / "map.png")


def test_main_window_export_image_writes_current_tab(qtbot, tmp_path: Path, monkeypatch):
    from genome_workbench.ui.main_window import MainWindow

    window = MainWindow(blast_work_dir=tmp_path / "blast_work")
    qtbot.addWidget(window)
    window.project_service.create_new(tmp_path / "proj.gwbproj", "Export Test")
    record = SequenceRecord(
        display_id="r1",
        sequence="ACGT" * 100,
        checksum_sha256="x",
        molecule_type=MoleculeType.DNA,
        topology=Topology.LINEAR,
    )
    window.project_service.get_repository().save_record(record)
    window._on_record_selected(record.id)
    window._tabs.setCurrentWidget(window.genome_map_page)

    out_path = tmp_path / "exported.png"
    monkeypatch.setattr(
        "genome_workbench.ui.main_window.QFileDialog.getSaveFileName",
        staticmethod(lambda *a, **k: (str(out_path), "PNG Image (*.png)")),
    )
    monkeypatch.setattr(
        "genome_workbench.ui.main_window.QInputDialog.getItem",
        staticmethod(lambda *a, **k: ("1x (screen resolution)", True)),
    )

    window._on_export_image_requested()

    assert out_path.exists()


def test_main_window_export_image_on_feature_table_tab_shows_message(
    qtbot, tmp_path: Path, monkeypatch
):
    from genome_workbench.ui.main_window import MainWindow

    window = MainWindow(blast_work_dir=tmp_path / "blast_work")
    qtbot.addWidget(window)
    window._tabs.setCurrentWidget(window.feature_table)

    info_calls = []
    monkeypatch.setattr(
        "genome_workbench.ui.main_window.QMessageBox.information",
        staticmethod(lambda *a, **k: info_calls.append(a)),
    )

    window._on_export_image_requested()

    assert info_calls
