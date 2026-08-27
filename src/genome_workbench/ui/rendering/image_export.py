"""Exports a genome/circular map widget to a PNG (raster, optionally
upscaled for print) or SVG (vector, infinitely scalable) file -- for
dropping a figure straight into a paper or slide deck without a screenshot
tool. Works on any QWidget by reusing its existing paintEvent through Qt's
own render() pipeline, so it stays in sync with on-screen rendering
automatically (no separate "export renderer" to keep up to date).
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtSvg import QSvgGenerator
from PySide6.QtWidgets import QWidget


class ImageExportError(RuntimeError):
    pass


def export_widget_as_image(widget: QWidget, path: Path, png_scale: int = 1) -> None:
    """Renders ``widget`` to ``path``. Format is chosen by the file extension
    (``.svg`` for vector, anything else -- typically ``.png`` -- for raster).
    ``png_scale`` multiplies the widget's current on-screen pixel size (2 or
    3 gives a much crisper result for print than a 1:1 screenshot, at the
    same visual layout).
    """
    if widget.width() <= 0 or widget.height() <= 0:
        raise ImageExportError("Nothing to export -- the view has no visible content yet.")

    if path.suffix.lower() == ".svg":
        _export_svg(widget, path)
    else:
        _export_png(widget, path, png_scale)


def _export_svg(widget: QWidget, path: Path) -> None:
    generator = QSvgGenerator()
    generator.setFileName(str(path))
    generator.setSize(widget.size())
    generator.setViewBox(QRect(0, 0, widget.width(), widget.height()))
    generator.setTitle(widget.windowTitle() or "GenomeWorkbench export")
    painter = QPainter(generator)
    try:
        widget.render(painter, QPoint(0, 0))
    finally:
        painter.end()


def _export_png(widget: QWidget, path: Path, scale: int) -> None:
    scale = max(1, scale)
    pixmap = QPixmap(widget.width() * scale, widget.height() * scale)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    try:
        painter.scale(scale, scale)
        widget.render(painter, QPoint(0, 0))
    finally:
        painter.end()
    if not pixmap.save(str(path), "PNG"):
        raise ImageExportError(f"Failed to write PNG to {path}")
